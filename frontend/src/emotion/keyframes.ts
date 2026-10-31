export interface VideoFrameInfo {
  fps: number
  frame_count: number
  duration_seconds: number
  frame_timestamps: number[]
  timestamp_basis: string
}

export function validKeyframes(onset:number,apex:number|null,offset:number|null,required:boolean,count=1800):boolean {
  return Number.isInteger(onset)&&onset>=1&&Number.isInteger(apex)&&apex!>onset&&apex!<=Math.min(count,1800)
    &&(!required||(Number.isInteger(offset)&&offset!>apex!&&offset!<=Math.min(count,1800)))
}

export function previewTime(info:VideoFrameInfo,frame:number):number {
  if(!Number.isInteger(frame)||frame<1||frame>info.frame_count)throw new RangeError('Invalid frame')
  return info.frame_timestamps[frame-1]??(frame-1)/info.fps
}
