import numpy as np
import pytest
from app.ml.micro_expression import spotting


def samples():
    times=np.arange(241)/30
    frames=np.arange(1,242)
    return times,frames


def pulse(times,start=2.,peak=3.,end=4.):
    return np.interp(times,[0,start,peak,end,8],[0,0,.12,0,0])


def test_static_curve_has_no_manufactured_triplet():
    times,frames=samples()
    result=spotting.select_intervals(times,np.zeros_like(times),frames)
    assert result['candidates']==[]
    assert result['reason']=='NO_CLEAR_MOVEMENT'


def test_triangle_returns_ordered_original_indices_and_requires_review():
    times,frames=samples()
    result=spotting.select_intervals(times,pulse(times),frames)
    candidate=result['candidates'][0]
    assert candidate['onset_frame'] < candidate['apex_frame'] < candidate['offset_frame']
    assert abs(candidate['apex_time']-3)<.15
    assert 1.7<candidate['onset_time']<2.4
    assert 3.6<candidate['offset_time']<4.3
    assert result['review_required'] is True
    assert result['status']=='REVIEW_REQUIRED'


def test_apex_uses_displacement_plateau_not_speed_peak():
    times,frames=samples()
    signal=np.interp(times,[0,2,2.3,3.4,4,8],[0,0,.15,.15,0,0])
    candidate=spotting.select_intervals(times,signal,frames)['candidates'][0]
    assert 2.4<candidate['apex_time']<3.3


def test_two_separate_expressions_require_explicit_selection():
    times,frames=samples()
    result=spotting.select_intervals(times,pulse(times,1,2,3)+pulse(times,4,5,6),frames)
    assert len(result['candidates'])==2
    assert result['status']=='MULTIPLE_CANDIDATES'
    assert result['review_required']


def test_incomplete_expression_is_not_closed_at_video_end():
    times,frames=samples()
    result=spotting.select_intervals(times,np.interp(times,[0,2,3,8],[0,0,.1,.1]),frames)
    assert result['candidates']==[]
    assert result['reason']=='INCOMPLETE_EXPRESSION'


def test_shifted_source_frames_are_not_replaced_by_sample_numbers():
    times,frames=samples()
    original=frames*2+5
    candidate=spotting.select_intervals(times,pulse(times),original)['candidates'][0]
    assert candidate['apex_frame'] in original
    assert abs(candidate['apex_frame']-187)<=6


@pytest.mark.parametrize('bad', [np.nan,np.inf])
def test_nonfinite_signal_rejected(bad):
    times,frames=samples()
    signal=pulse(times);signal[20]=bad
    with pytest.raises(ValueError):spotting.select_intervals(times,signal,frames)


def test_head_motion_quality_rejects_without_hiding_reason():
    times,frames=samples()
    result=spotting.select_intervals(times,pulse(times),frames,quality={'head_motion_excessive':True})
    assert result['candidates']==[]
    assert result['reason']=='HEAD_MOTION'


def test_single_frame_impulse_is_not_a_stable_expression():
    times,frames=samples()
    signal=np.zeros_like(times);signal[90]=.2
    assert spotting.select_intervals(times,signal,frames)['candidates']==[]



def test_brief_excessive_head_excursion_is_not_hidden_by_whole_clip_percentile():
    residual=np.zeros(900);residual[450:456]=.12
    assert np.percentile(residual,90)==0
    assert spotting.excessive_head_motion(residual)


def test_single_tracking_glitch_is_not_sustained_head_movement():
    residual=np.zeros(900);residual[450]=.12
    assert not spotting.excessive_head_motion(residual)


def test_blink_only_landmarks_have_zero_expression_displacement():
    rng=np.random.default_rng(9)
    reference=rng.uniform(50,150,size=(468,2))
    reference[33]=[60,80];reference[263]=[140,80]
    samples=np.repeat(reference[None],90,axis=0)
    samples[30:36,[159,145,386,374],1]+=10
    signal=spotting.landmark_displacement(samples,np.arange(90)/30)
    np.testing.assert_allclose(signal,0,atol=1e-8)


def test_similarity_stabilizes_rigid_camera_motion_before_signal():
    rng=np.random.default_rng(11)
    reference=rng.uniform(50,150,size=(468,2))
    reference[33]=[60,80];reference[263]=[140,80]
    samples=[]
    for i in range(90):
        angle=.1*np.sin(i/10)
        rotation=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
        moved=reference@rotation*(1+.05*np.sin(i/8))+[i/5,-i/6]
        aligned,residual=spotting.align_landmarks(moved,reference)
        assert residual<1e-8
        samples.append(aligned)
    signal=spotting.landmark_displacement(np.array(samples),np.arange(90)/30)
    np.testing.assert_allclose(signal,0,atol=1e-8)
