"""CausalNet author-derived flow protocol and versioned video face alignment.

Flow: author's issue #3/#4 (TV-L1, per-channel min/max, OS/V/U, no clipping).
Face alignment is our explicit adapter, not claimed to reproduce unpublished
training crops. Input FPS is preserved; no frame interpolation is performed.
"""
from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np

PREPROCESS_VERSION = 'causalnet-tvl1-osvu-facealign-v1'


class VideoInputError(ValueError):
    pass


def validate_frames(onset, apex, offset):
    if (any(isinstance(x,bool) or not isinstance(x,int) for x in (onset,apex,offset))
            or not 1 <= onset < apex < offset <= 1800):
        raise VideoInputError('请填写起始帧 < 峰值帧 < 结束帧，范围为 1～1800。')


def decode_video(path: Path, selected=None):
    """Sequential decoding; never trust frame-count metadata or seek indices."""
    if selected is not None:
        validate_frames(*selected)
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise VideoInputError('视频不可解码，请使用有效的视频文件。')
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        if not math.isfinite(fps) or not 1 <= fps <= 240:
            raise VideoInputError('视频帧率无效。')
        timestamps, frames = [], []
        limit = selected[-1] if selected else 1801
        for index in range(1,limit+1):
            ok, frame = capture.read()
            if not ok:
                break
            if max(frame.shape[:2])>3840 or min(frame.shape[:2])>2160:
                raise VideoInputError('视频分辨率最高支持 3840×2160。')
            timestamp = float(capture.get(cv2.CAP_PROP_POS_MSEC))/1000
            timestamps.append(timestamp if math.isfinite(timestamp) and timestamp>=0 else (index-1)/fps)
            if selected and index in selected:
                frames.append(frame)
        if selected:
            if len(frames)!=3:
                raise VideoInputError('所选关键帧超过视频实际长度。')
            return frames, fps
        if len(timestamps)<3:
            raise VideoInputError('视频至少需要 3 帧。')
        if len(timestamps)>1800:
            raise VideoInputError('视频最多支持 1800 帧，请先截取表情片段。')
        # Some decoders do not expose timestamps. Explicitly report fallback.
        measured = all(timestamps[i]>timestamps[i-1] for i in range(1,len(timestamps)))
        if not measured:
            timestamps = [i/fps for i in range(len(timestamps))]
        return dict(fps=fps,frame_count=len(timestamps),duration_seconds=len(timestamps)/fps,
                    frame_timestamps=timestamps,timestamp_basis='decoded' if measured else 'nominal_fps')
    finally:
        capture.release()


def optical_strain(u, v):
    # NumPy equivalent of the author's pandas shift(-1) + ffill axes 1,0.
    ux = u[:,:-1]-u[:,1:]
    vy = v[:-1,:]-v[1:,:]
    uy = u[:-1,:]-u[1:,:]
    vx = v[:,:-1]-v[:,1:]
    strain = np.sqrt(ux[:-1]**2 + vy[:,:-1]**2 + .25*(uy[:,:-1]+vx[:-1])**2)
    return np.pad(strain,((0,1),(0,1)),mode='edge')


def normalize_channel(value):
    span = float(value.max()-value.min())
    if span == 0:
        return value.astype(np.uint8)
    return ((value-value.min())/span*255).astype(np.uint8)


def encode_flow(flow):
    magnitude, angle = cv2.cartToPolar(flow[...,0],flow[...,1])
    # Preserve author's polar round trip before computing optical strain.
    u, v = magnitude*np.cos(angle), magnitude*np.sin(angle)
    os_ = optical_strain(u,v)
    norm_u, norm_v, norm_os = [normalize_channel(cv2.resize(a,(48,48))) for a in (u,v,os_)]
    feature = np.stack([norm_os,norm_v,norm_u],axis=-1)
    _, direction = cv2.cartToPolar(norm_u.astype(np.float32),norm_v.astype(np.float32))
    hsv = np.full((48,48,3),255,dtype=np.uint8)
    hsv[...,0] = (direction*180/np.pi/2).astype(np.uint8)
    colors = cv2.cvtColor(hsv,cv2.COLOR_HSV2BGR)
    return cv2.resize(feature,(28,28)), cv2.resize(colors,(28,28))


def pack_regions(images):
    # Coordinates exactly match main_train.py after clamp(7,21).astype(int).
    coords = [(9,11),(10,21),(21,10),(20,21)]
    packed = []
    for image in images:
        if image.shape!=(28,28,3) or image.dtype!=np.uint8:
            raise ValueError('Invalid CausalNet encoded feature image')
        parts = [image[y-7:y+7,x-7:x+7] for x,y in coords]
        tile = np.concatenate([np.concatenate(parts[:2],axis=1),np.concatenate(parts[2:],axis=1)],axis=0)
        packed.append(tile.transpose(2,0,1))
    result = np.stack(packed).astype(np.float32)
    if result.shape!=(4,3,28,28) or not np.isfinite(result).all():
        raise ValueError('Invalid CausalNet four-input tensor')
    return result


class FaceAligner:
    """Real single-face detection; no dummy coordinates or silent fallback."""
    def __init__(self):
        import mediapipe as mp
        self.detector = mp.solutions.face_detection.FaceDetection(model_selection=0,min_detection_confidence=.7)

    def close(self):
        self.detector.close()

    def _upright(self, frame, rotation=None):
        """Detect actual eye/mouth geometry, including phone files without tags.

        Try only quarter turns; do not mistake an upside-down face for upright
        just because its eye line is horizontal. Reuse the onset's rotation.
        """
        for degrees in ((rotation,) if rotation is not None else (0,90,180,270)):
            candidate=np.rot90(frame,degrees//90).copy() if degrees else frame
            height,width=candidate.shape[:2]
            scale=min(1.,1280/max(height,width))
            small=cv2.resize(candidate,(round(width*scale),round(height*scale))) if scale<1 else candidate
            detections=self.detector.process(cv2.cvtColor(small,cv2.COLOR_BGR2RGB)).detections or []
            if len(detections)!=1:continue
            det=detections[0]
            p=det.location_data.relative_keypoints
            dx=(p[1].x-p[0].x)*width;dy=(p[1].y-p[0].y)*height
            distance=math.hypot(dx,dy)
            mouth=(p[3].y-(p[0].y+p[1].y)/2)*height
            if distance>=16 and abs(dy)<distance*.6 and mouth>distance*.25:
                self.orientation=degrees
                return candidate,det
        raise VideoInputError('每个关键帧须为清晰、完整的单人正面面部。')

    def align(self, frame, rotation=None):
        frame,det=self._upright(frame,rotation)
        height,width = frame.shape[:2]
        box = det.location_data.relative_bounding_box
        if min(box.width*width,box.height*height)<64:
            raise VideoInputError('人脸过小，请靠近镜头后重试。')
        points = det.location_data.relative_keypoints
        eyes = sorted([(points[i].x*width,points[i].y*height) for i in (0,1)])
        left,right = np.asarray(eyes,dtype=np.float32)
        delta=right-left
        distance=float(np.linalg.norm(delta))
        if distance<16 or abs(float(delta[1]))>distance*.6:
            raise VideoInputError('请正对镜头，保持头部平稳。')
        # Match the supplied 28px feature layout at 224px; same canonical
        # target for all three independently detected frames.
        a,b = 96*delta[0]/distance**2,96*delta[1]/distance**2
        transform = np.array([[a,b,72-a*left[0]-b*left[1]],[-b,a,88+b*left[0]-a*left[1]]],dtype=np.float32)
        corners=cv2.transform(np.array([[[0,0],[223,0],[0,223],[223,223]]],dtype=np.float32),cv2.invertAffineTransform(transform))[0]
        if (corners[:,0].min()<0 or corners[:,1].min()<0 or corners[:,0].max()>=width or corners[:,1].max()>=height):
            raise VideoInputError('面部周围空间不足，请让完整面部入镜。')
        return cv2.warpAffine(frame,transform,(224,224)), float(det.score[0])


def prepare_video(path, onset, apex, offset, aligner):
    frames,fps=decode_video(path,(onset,apex,offset))
    aligned,scores=[],[]
    rotation=None
    for frame in frames:
        face,score=aligner.align(frame,rotation=rotation)
        rotation=aligner.orientation
        aligned.append(cv2.cvtColor(face,cv2.COLOR_BGR2GRAY));scores.append(score)
    if not hasattr(cv2,'optflow') or not hasattr(cv2.optflow,'DualTVL1OpticalFlow_create'):
        raise ValueError('CausalNet requires OpenCV contrib TV-L1; no fallback')
    optical=cv2.optflow.DualTVL1OpticalFlow_create()
    flow1=optical.calc(aligned[0],aligned[1],None)
    flow2=optical.calc(aligned[1],aligned[2],None)
    if not all(np.isfinite(flow).all() for flow in (flow1,flow2)):
        raise VideoInputError('光流计算无效，请重新选择清晰的表情片段。')
    motion = max(float(np.mean(np.linalg.norm(f,axis=2))) for f in (flow1,flow2))
    if motion < .001:
        raise VideoInputError('关键帧之间没有足够的面部运动，请重新选择表情片段。')
    first,direction1=encode_flow(flow1)
    second,direction2=encode_flow(flow2)
    return pack_regions([first,second,direction1,direction2]),dict(
        status='VALID_KEYFRAMES',fps=fps,onset_frame=onset,apex_frame=apex,offset_frame=offset,
        face_detection_scores=scores,mean_motion_pixels=motion,preprocessing_version=PREPROCESS_VERSION,
        face_alignment='mediapipe-eyes-canonical-v1',orientation_degrees=rotation,flow_method='tvl1',
        training_crop_equivalence_verified=False,clinical_eligible=False,
        low_frame_rate_input=fps<90)
