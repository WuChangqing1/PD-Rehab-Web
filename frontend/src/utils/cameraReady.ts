/** Optional camera enumeration must never gate preview readiness. */
export async function readyCamera(preview:()=>Promise<unknown>, ready:()=>void, enumerate:()=>Promise<unknown>):Promise<void> {
  await preview()
  ready()
  void enumerate().catch(()=>{})
}
