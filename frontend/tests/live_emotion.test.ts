import { test } from 'node:test'
import assert from 'node:assert/strict'
import { validDistribution, nextSimulationBpm } from '../src/emotion/types.ts'
import { ChunkBackpressure } from '../src/emotion/streamClient.ts'

test('simulation cannot change difficulty outside boundary or official mode', () => {
  const result = { source:'SIMULATED', quality:'GOOD', probabilities:[.05,.35,.05,.35,.05,.1,.05], result_timestamp_ms:1000 }
  assert.equal(nextSimulationBpm(60, true, true, result,1000),80)
  assert.equal(nextSimulationBpm(60, false, true, result,1000),60)
  assert.equal(nextSimulationBpm(60, true, false, result,1000),60)
  assert.equal(nextSimulationBpm(60, true, true, result,40000),60)
  assert.equal(nextSimulationBpm(120, true, true, result,1000),120)
  assert.equal(validDistribution([NaN,0,0,0,0,0,1]),false)
  assert.equal(validDistribution([1]),false)
})

test('backpressure has one in-flight slot and rejects oversized chunks', () => {
  const gate = new ChunkBackpressure()
  assert.equal(gate.take(100),true)
  assert.equal(gate.take(100),false)
  gate.ack()
  assert.equal(gate.take(3*1024*1024),false)
  assert.equal(gate.take(100),true)
})
