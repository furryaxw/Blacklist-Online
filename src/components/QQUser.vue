<template>
  <n-tag
      v-if="qq"
      :bordered="false"
      size="small"
      class="qq-tag"
      @click.stop="handleClick"
  >
    <!--    <template #icon>
          <span class="qq-icon">👤</span>
        </template>-->
    {{ qq }}
  </n-tag>
  <span v-else>-</span>
</template>

<script setup lang="ts">
import {NTag} from 'naive-ui'
import {uiStore} from '../store/ui'

const props = defineProps<{
  qq?: string | number
}>()

const handleClick = () => {
  if (props.qq) {
    uiStore.openProfile(props.qq)
  }
}
</script>

<style scoped>
.qq-tag {
  cursor: pointer;
  background-color: rgba(99, 102, 241, 0.1); /* 淡淡的靛蓝色背景 */
  color: var(--n-primary-color);
  font-family: monospace;
  transition: all 0.2s;
  user-select: none;
}

.qq-tag:hover {
  background-color: var(--n-primary-color);
  color: #fff;
  transform: translateY(-1px);
}

.qq-icon {
  margin-right: 2px;
  font-size: 12px;
}
</style>