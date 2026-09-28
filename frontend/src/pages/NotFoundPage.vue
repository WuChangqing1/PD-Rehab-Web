<script setup lang="ts">
/**
 * 404 page.
 */
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="not-found">
    <el-result icon="warning" title="页面不存在" sub-title="请检查地址是否正确，或返回工作台。">
      <template #extra>
        <el-button type="primary" @click="router.push('/dashboard')">返回工作台</el-button>
      </template>
    </el-result>
  </div>
</template>

<style scoped>
.not-found {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: var(--pd-bg);
}
</style>
