import { cp, mkdir } from 'node:fs/promises';
await mkdir('web/cesium', { recursive: true });
await cp('node_modules/cesium/Build/Cesium', 'web/cesium', { recursive: true });
