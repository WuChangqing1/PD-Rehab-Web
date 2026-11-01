"""Review-only short-clip spotting baseline, not a reproduction of DMA.

Multi-scale contrast and interval aggregation are inspired by DMA-ME-Spotting.
The displacement signal, MediaPipe tracking and gates are this adapter's own.
No temporal FPS interpolation or classification weights are used here.
"""
from __future__ import annotations

import math
from pathlib import Path
import cv2
import numpy as np

VERSION = 'face-displacement-multiscale-v1'
REASONS = {
    'NO_CLEAR_MOVEMENT': '未找到清晰的完整面部变化，请重新录制或由医生手动选择。',
    'INCOMPLETE_EXPRESSION': '表情变化缺少平稳的开始或结束，请完整录制后重试。',
    'HEAD_MOTION': '头部变化较大，请保持正对镜头后重新录制。',
    'FACE_NOT_VISIBLE': '请保持单人面部完整入镜后重新录制。',
}


def _response(candidates=None, reason=None, quality=None):
    candidates = candidates or []
    return dict(algorithm_version=VERSION, review_required=True,
        status=('MULTIPLE_CANDIDATES' if len(candidates)>1 else 'REVIEW_REQUIRED') if candidates else 'NO_CANDIDATE',
        candidates=candidates, reason=reason,
        message=REASONS.get(reason, '请由操作者确认候选画面，再开始分析。'),
        quality=quality or {})


def select_intervals(times, signal, frames, quality=None):
    """Find complete displacement excursions; never replace missing boundaries."""
    times=np.asarray(times,dtype=float)
    signal=np.asarray(signal,dtype=float)
    frames=np.asarray(frames)
    if (times.ndim!=1 or times.shape!=signal.shape or frames.shape!=times.shape or len(times)<7
            or not np.isfinite(times).all() or not np.isfinite(signal).all()
            or not np.all(np.diff(times)>0) or not np.all(np.diff(frames)>0)
            or not np.issubdtype(frames.dtype,np.integer) or frames[0]<1 or frames[-1]>1800):
        raise ValueError('Invalid sampled displacement track')
    quality=dict(quality or {})
    if quality.get('head_motion_excessive'):
        return _response(reason='HEAD_MOTION',quality=quality)
    dt=float(np.median(np.diff(times)))
    window=max(3,int(round(.1/dt))|1)
    window=min(window,9)
    pad=window//2
    padded=np.pad(signal,(pad,pad),mode='edge')
    smooth=np.array([np.median(padded[i:i+window]) for i in range(len(signal))])
    baseline_count=max(3,int(round(.3/dt)))
    baseline=smooth[:baseline_count]
    noise=float(np.median(np.abs(baseline-np.median(baseline)))*1.4826)
    floor=max(.006,noise*3)
    high=max(.018,noise*6)
    values=np.maximum(smooth-float(np.median(baseline)),0)
    quality.update(noise_floor=round(noise,6),signal_threshold=round(high,6),
        sampled_frames=len(times),signal_kind='aligned_landmark_displacement')
    if float(values.max())<high:
        return _response(reason='NO_CLEAR_MOVEMENT',quality=quality)
    active=values>floor
    edges=np.diff(np.r_[False,active,False].astype(int))
    spans=list(zip(np.where(edges==1)[0],np.where(edges==-1)[0]-1))
    candidates=[];incomplete=False
    for left,right in spans:
        local=values[left:right+1]
        peak_value=float(local.max())
        if peak_value<high or times[right]-times[left]<.06:
            continue
        # At least 0.1 sec of quiet support outside both boundaries.
        quiet=max(2,int(round(.1/dt)))
        if left<quiet or right+quiet>=len(times):
            incomplete=True;continue
        boundary=max(floor,peak_value*.12)
        peak=int(left+np.argmax(local))
        onset=peak
        while onset>0 and values[onset]>boundary:onset-=1
        offset=peak
        while offset<len(values)-1 and values[offset]>boundary:offset+=1
        if onset<quiet or offset+quiet>=len(values):
            incomplete=True;continue
        # Select the center of the high-displacement plateau, not its speed.
        plateau=np.where(values[onset:offset+1]>=peak_value*.95)[0]+onset
        apex=int(plateau[len(plateau)//2])
        if not onset<apex<offset:continue
        contrasts=[]
        for seconds in (.1,.25,.5):
            radius=max(1,round(seconds/dt))
            lo=max(0,apex-radius);hi=min(len(values),apex+radius+1)
            flank=np.r_[values[max(0,lo-radius):lo],values[hi:min(len(values),hi+radius)]]
            contrasts.append(float(values[lo:hi].mean()-(flank.mean() if len(flank) else 0)))
        candidates.append(dict(id=f'candidate-{len(candidates)+1}',
            onset_frame=int(frames[onset]),apex_frame=int(frames[apex]),offset_frame=int(frames[offset]),
            onset_time=round(float(times[onset]),6),apex_time=round(float(times[apex]),6),
            offset_time=round(float(times[offset]),6),
            duration_seconds=round(float(times[offset]-times[onset]),3),
            displacement_peak=round(peak_value,6),
            multiscale_contrast=[round(x,6) for x in contrasts]))
    quality['candidate_count']=len(candidates)
    if len(candidates)>5:
        return _response(reason='HEAD_MOTION',quality=quality|{'too_many_intervals':True})
    return _response(candidates,('INCOMPLETE_EXPRESSION' if incomplete else 'NO_CLEAR_MOVEMENT')
        if not candidates else None,quality)


ANCHORS=np.array([33,133,362,263,1,168])
EXPRESSION=np.array([61,291,0,17,13,14,78,308,70,63,105,66,107,336,296,334,293,300])


def align_landmarks(points, reference):
    """Least-squares similarity removes rigid camera translation/rotation/scale."""
    source=points[ANCHORS];target=reference[ANCHORS]
    x=source-source.mean(axis=0);y=target-target.mean(axis=0)
    u,s,vt=np.linalg.svd(x.T@y)
    if np.linalg.det(u@vt)<0:
        u[:,-1]*=-1;s[-1]*=-1
    rotation=u@vt
    scale=float(s.sum()/max(float((x*x).sum()),1e-12))
    aligned=(points-source.mean(axis=0))@rotation*scale+target.mean(axis=0)
    eye=float(np.linalg.norm(reference[33]-reference[263]))
    residual=float(np.sqrt(np.mean(np.sum((aligned[ANCHORS]-target)**2,axis=1)))/max(eye,1e-6))
    return aligned,residual


def excessive_head_motion(residuals):
    values=np.asarray(residuals,dtype=float)
    if not len(values) or not np.isfinite(values).all():return True
    sustained=np.convolve((values>.06).astype(int),np.ones(3,dtype=int),mode='valid')
    return bool(np.percentile(values,90)>.06 or (sustained>=2).any())


def landmark_displacement(samples,times):
    samples=np.asarray(samples)
    dt=max(float(np.median(np.diff(times))),.001)
    baseline=np.median(samples[:max(3,round(.3/dt))],axis=0)
    eye=float(np.linalg.norm(baseline[33]-baseline[263]))
    return np.sqrt(np.mean(np.sum((samples[:,EXPRESSION]-baseline[EXPRESSION])**2,axis=2),axis=1))/max(eye,1e-6)


def extract_track(path:Path, aligner):
    from causalnet_preprocess import decode_video,VideoInputError
    import mediapipe as mp
    info=decode_video(path)
    if info['duration_seconds']>30.5:
        raise VideoInputError('自动选帧支持 30 秒以内的视频，请截取一次完整变化或使用手动选帧。')
    capture=cv2.VideoCapture(str(path))
    sampled=[];times=[];frames=[];residuals=[];next_sample=0.;reference=None;rotation=None
    mesh=mp.solutions.face_mesh.FaceMesh(static_image_mode=False,max_num_faces=2,
        refine_landmarks=False,min_detection_confidence=.7,min_tracking_confidence=.7)
    try:
        for number,timestamp in enumerate(info['frame_timestamps'],1):
            ok,frame=capture.read()
            if not ok:raise VideoInputError('视频解码不完整，请重新选择视频。')
            if timestamp+1e-6<next_sample:continue
            next_sample=timestamp+1/30
            if rotation is None:
                try:
                    frame,_=aligner._upright(frame)
                    rotation=aligner.orientation
                except VideoInputError:
                    return info,None,'FACE_NOT_VISIBLE'
            elif rotation:
                frame=np.rot90(frame,rotation//90).copy()
            height,width=frame.shape[:2]
            scale=min(1.,640/max(height,width))
            image=cv2.resize(frame,(round(width*scale),round(height*scale)))
            result=mesh.process(cv2.cvtColor(image,cv2.COLOR_BGR2RGB))
            if not result.multi_face_landmarks or len(result.multi_face_landmarks)!=1:
                return info,None,'FACE_NOT_VISIBLE'
            points=np.array([(p.x*image.shape[1],p.y*image.shape[0]) for p in result.multi_face_landmarks[0].landmark])
            if reference is None:reference=points.copy()
            aligned,residual=align_landmarks(points,reference)
            sampled.append(aligned);residuals.append(residual);frames.append(number);times.append(timestamp)
        if len(sampled)<7:raise VideoInputError('视频过短，请录制完整的面部变化。')
    finally:
        mesh.close();capture.release()
    sampled=np.asarray(sampled)
    displacement=landmark_displacement(sampled,times)
    quality=dict(orientation_degrees=rotation,head_motion_excessive=excessive_head_motion(residuals),
        rigid_residual_max=round(float(np.max(residuals)),6),
        rigid_residual_p90=round(float(np.percentile(residuals,90)),6),eye_blink_regions_excluded=True,
        training_crop_equivalence_verified=False,clinical_eligible=False)
    return info,dict(times=times,frames=frames,signal=displacement.tolist(),quality=quality),None


def spot_video(path,aligner):
    info,track,reason=extract_track(Path(path),aligner)
    if track is None:
        result=_response(reason=reason)
    else:
        result=select_intervals(track['times'],track['signal'],track['frames'],track['quality'])
        step=max(1,math.ceil(len(track['times'])/180))
        result['signal_preview']=[dict(time=round(t,4),displacement=round(s,6))
            for t,s in zip(track['times'][::step],track['signal'][::step])]
    result['video_info']=info
    return result
