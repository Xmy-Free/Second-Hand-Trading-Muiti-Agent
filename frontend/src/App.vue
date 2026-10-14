<script setup lang="ts">
import zhCn from 'element-plus/es/locale/lang/zh-cn'
</script>

<template>
  <el-config-provider :locale="zhCn">
    <router-view v-slot="{ Component, route }">
      <transition name="page-fade" mode="out-in">
        <component
          :is="Component"
          :key="route.matched[0]?.path ?? route.path"
        />
      </transition>
    </router-view>
  </el-config-provider>
</template>
