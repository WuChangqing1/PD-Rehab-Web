/** Continuous MediaRecorder container protocol: never reinterpret chunks as still images. */
export class ChunkBackpressure {
  private pending = false
  take(bytes:number):boolean {
    if (this.pending || bytes <= 0 || bytes > 2*1024*1024) return false
    this.pending = true
    return true
  }
  ack() { this.pending = false }
}

export class EmotionStreamClient {
  private socket:WebSocket|null = null
  private gate = new ChunkBackpressure()
  private seq = 0
  private deadline:ReturnType<typeof setTimeout>|null = null
  onMessage:(value:Record<string,unknown>)=>void = () => {}
  onFailure:()=>void = () => {}
  connect(url:string, token:string, sessionId:string, patientId:string, simulationDemo=false) {
    this.close()
    const socket = this.socket = new WebSocket(url)
    this.deadline = setTimeout(() => this.fail(),8000)
    socket.onopen = () => socket.send(JSON.stringify({type:'auth',token,session_id:sessionId,patient_id:patientId,simulation_demo:simulationDemo}))
    socket.onmessage = event => {
      try {
        const data = JSON.parse(String(event.data)) as Record<string,unknown>
        if (this.deadline) clearTimeout(this.deadline)
        this.deadline = null
        if (data.type === 'ack') this.gate.ack()
        this.onMessage(data)
      } catch { this.fail() }
    }
    socket.onerror = () => this.fail()
    socket.onclose = () => this.fail()
  }
  sendChunk(blob:Blob,capturedAt:number,durationMs:number):boolean {
    const socket = this.socket
    if (!socket || socket.readyState !== WebSocket.OPEN || socket.bufferedAmount > 0 || !this.gate.take(blob.size)) return false
    socket.send(JSON.stringify({type:'chunk',seq:this.seq++,capture_timestamp_ms:capturedAt,duration_ms:durationMs,byte_length:blob.size,mime_type:blob.type}))
    socket.send(blob)
    this.deadline = setTimeout(() => this.fail(),10000)
    return true
  }
  private fail() { this.close(); this.onFailure() }
  close() {
    if (this.deadline) clearTimeout(this.deadline)
    this.deadline = null
    if (this.socket) {
      this.socket.onclose = null
      this.socket.onerror = null
      this.socket.onmessage = null
      this.socket.onopen = null
      this.socket.close()
    }
    this.socket = null
    this.gate.ack()
    this.seq = 0
  }
}
