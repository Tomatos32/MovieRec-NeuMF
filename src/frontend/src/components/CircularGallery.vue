<template>
  <div ref="containerRef" class="w-full h-full overflow-hidden cursor-grab active:cursor-grabbing" />
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, watch, useTemplateRef } from 'vue';
import { Camera, Mesh, Plane, Program, Renderer, Texture, Transform } from 'ogl';

interface CircularGalleryProps {
  items?: { image: string; text: string; value?: string }[];
  bend?: number;
  textColor?: string;
  borderRadius?: number;
  font?: string;
  scrollSpeed?: number;
  scrollEase?: number;
}

const props = withDefaults(defineProps<CircularGalleryProps>(), {
  bend: 3,
  textColor: '#ffffff',
  borderRadius: 0.05,
  font: 'bold 30px Figtree',
  scrollSpeed: 2,
  scrollEase: 0.05
});

const emit = defineEmits(['select']);

const containerRef = useTemplateRef<HTMLDivElement>('containerRef');
let app: App | null = null;

type GL = Renderer['gl'];

function debounce<T extends (...args: unknown[]) => void>(func: T, wait: number) {
  let timeout: number;
  return function (this: unknown, ...args: Parameters<T>) {
    window.clearTimeout(timeout);
    timeout = window.setTimeout(() => func.apply(this, args), wait);
  };
}

function lerp(p1: number, p2: number, t: number): number {
  return p1 + (p2 - p1) * t;
}

function autoBind(instance: any): void {
  const proto = Object.getPrototypeOf(instance);
  if (!proto) return;
  Object.getOwnPropertyNames(proto).forEach(key => {
    if (key !== 'constructor') {
      const desc = Object.getOwnPropertyDescriptor(proto, key);
      if (desc && typeof desc.value === 'function') {
        instance[key] = instance[key].bind(instance);
      }
    }
  });
}

function getFontSize(font?: string): number {
  if (!font) return 30;
  const match = font.match(/(\d+)px/);
  return match && match[1] ? parseInt(match[1], 10) : 30;
}

function createTextTexture(
  gl: GL,
  text: string,
  font: string = 'bold 30px Figtree',
  color: string = 'white'
): { texture: Texture; width: number; height: number } {
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');
  if (!context) throw new Error('Could not get 2d context');

  context.font = font;
  const metrics = context.measureText(text);
  const textWidth = Math.ceil(metrics.width);
  const fontSize = getFontSize(font);
  const textHeight = Math.ceil(fontSize * 1.2);

  canvas.width = textWidth + 20;
  canvas.height = textHeight + 20;

  context.font = font;
  context.fillStyle = color;
  context.textBaseline = 'middle';
  context.textAlign = 'center';
  context.clearRect(0, 0, canvas.width, canvas.height);
  context.fillText(text, canvas.width / 2, canvas.height / 2);

  const texture = new Texture(gl, { generateMipmaps: false });
  texture.image = canvas;
  return { texture, width: canvas.width, height: canvas.height };
}

interface TitleProps {
  gl: GL;
  plane: Mesh;
  renderer: Renderer;
  text: string;
  textColor?: string;
  font?: string;
}

class Title {
  gl: GL;
  plane: Mesh;
  renderer: Renderer;
  text: string;
  textColor: string;
  font: string;
  mesh!: Mesh;
  aspect!: number;

  constructor({ gl, plane, renderer, text, textColor = '#ffffff', font = '30px Figtree' }: TitleProps) {
    this.gl = gl;
    this.plane = plane;
    this.renderer = renderer;
    this.text = text;
    this.textColor = textColor;
    this.font = font;
    this.createMesh();
  }

  createMesh() {
    const { texture, width, height } = createTextTexture(this.gl, this.text, this.font, this.textColor);
    this.aspect = width / height;
    
    const geometry = new Plane(this.gl);
    const program = new Program(this.gl, {
      vertex: `
        attribute vec3 position;
        attribute vec2 uv;
        uniform mat4 modelViewMatrix;
        uniform mat4 projectionMatrix;
        varying vec2 vUv;
        void main() {
          vUv = uv;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragment: `
        precision highp float;
        uniform sampler2D tMap;
        varying vec2 vUv;
        void main() {
          vec4 color = texture2D(tMap, vUv);
          if (color.a < 0.1) discard;
          gl_FragColor = color;
        }
      `,
      uniforms: { tMap: { value: texture } },
      transparent: true
    });
    this.mesh = new Mesh(this.gl, { geometry, program });
    // 初始化随意放置，具体的坐标和缩放交由 onResize 来进行 local-space 的安全计算
    this.mesh.setParent(this.plane);
  }
}

interface MediaProps {
  geometry: Plane;
  gl: GL;
  image: string;
  index: number;
  length: number;
  renderer: Renderer;
  scene: Transform;
  screen: { width: number, height: number };
  text: string;
  value?: string;
  viewport: { width: number, height: number };
  bend: number;
  textColor: string;
  borderRadius?: number;
  font?: string;
}

class Media {
  extra: number = 0;
  geometry: Plane;
  gl: GL;
  image: string;
  index: number;
  length: number;
  renderer: Renderer;
  scene: Transform;
  screen: { width: number, height: number };
  text: string;
  value?: string;
  viewport: { width: number, height: number };
  bend: number;
  textColor: string;
  borderRadius: number;
  font: string;
  program!: Program;
  plane!: Mesh;
  title!: Title;
  scale!: number;
  padding!: number;
  width!: number;
  widthTotal!: number;
  x!: number;
  speed: number = 0;
  isBefore: boolean = false;
  isAfter: boolean = false;

  constructor({
    geometry,
    gl,
    image,
    index,
    length,
    renderer,
    scene,
    screen,
    text,
    value,
    viewport,
    bend,
    textColor,
    borderRadius = 0,
    font = 'bold 30px Figtree'
  }: MediaProps) {
    this.geometry = geometry;
    this.gl = gl;
    this.image = image;
    this.index = index;
    this.length = length;
    this.renderer = renderer;
    this.scene = scene;
    this.screen = screen;
    this.text = text;
    this.value = value;
    this.viewport = viewport;
    this.bend = bend;
    this.textColor = textColor;
    this.borderRadius = borderRadius;
    this.font = font;
    this.createShader();
    this.createMesh();
    this.createTitle();
    this.onResize();
  }

  createShader() {
    const texture = new Texture(this.gl, { generateMipmaps: false });
    this.program = new Program(this.gl, {
      depthTest: false,
      depthWrite: false,
      vertex: `
        precision highp float;
        attribute vec3 position;
        attribute vec2 uv;
        uniform mat4 modelViewMatrix;
        uniform mat4 projectionMatrix;
        uniform float uTime;
        uniform float uSpeed;
        varying vec2 vUv;
        void main() {
          vUv = uv;
          vec3 p = position;
          p.z = (sin(p.x * 4.0 + uTime) * 1.5 + cos(p.y * 2.0 + uTime) * 1.5) * (0.1 + uSpeed * 0.5);
          gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
        }
      `,
      fragment: `
        precision highp float;
        uniform vec2 uImageSizes;
        uniform vec2 uPlaneSizes;
        uniform sampler2D tMap;
        uniform float uBorderRadius;
        varying vec2 vUv;
        
        float roundedBoxSDF(vec2 p, vec2 b, float r) {
          vec2 d = abs(p) - b;
          return length(max(d, vec2(0.0))) + min(max(d.x, d.y), 0.0) - r;
        }
        
        void main() {
          vec2 ratio = vec2(
            min((uPlaneSizes.x / uPlaneSizes.y) / (uImageSizes.x / uImageSizes.y), 1.0),
            min((uPlaneSizes.y / uPlaneSizes.x) / (uImageSizes.y / uImageSizes.x), 1.0)
          );
          vec2 uv = vec2(
            vUv.x * ratio.x + (1.0 - ratio.x) * 0.5,
            vUv.y * ratio.y + (1.0 - ratio.y) * 0.5
          );
          vec4 color = texture2D(tMap, uv);
          
          float d = roundedBoxSDF(vUv - 0.5, vec2(0.5 - uBorderRadius), uBorderRadius);
          if(d > 0.0) {
            discard;
          }
          
          gl_FragColor = vec4(color.rgb, 1.0);
        }
      `,
      uniforms: {
        tMap: { value: texture },
        uPlaneSizes: { value: [0, 0] },
        uImageSizes: { value: [0, 0] },
        uSpeed: { value: 0 },
        uTime: { value: 100 * Math.random() },
        uBorderRadius: { value: this.borderRadius }
      },
      transparent: true
    });
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.src = this.image;
    img.onload = () => {
      // 缩放处理 / Image downscaling before embedding
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      const MAX_WIDTH = 512;
      const MAX_HEIGHT = 512;
      let width = img.naturalWidth;
      let height = img.naturalHeight;
      if (width > MAX_WIDTH || height > MAX_HEIGHT) {
          const ratio = Math.min(MAX_WIDTH / width, MAX_HEIGHT / height);
          width = width * ratio;
          height = height * ratio;
      }
      canvas.width = width;
      canvas.height = height;
      ctx?.drawImage(img, 0, 0, width, height);

      texture.image = canvas;
      this.program.uniforms.uImageSizes.value = [width, height];
    };
  }

  createMesh() {
    this.plane = new Mesh(this.gl, {
      geometry: this.geometry,
      program: this.program
    });
    this.plane.setParent(this.scene);
  }

  createTitle() {
    this.title = new Title({
      gl: this.gl,
      plane: this.plane,
      renderer: this.renderer,
      text: this.text,
      textColor: this.textColor,
      font: this.font
    });
  }

  update(scroll: { current: number; last: number }, direction: 'right' | 'left') {
    this.plane.position.x = this.x - scroll.current - this.extra;

    const x = this.plane.position.x;
    const H = this.viewport.width / 2;

    if (this.bend === 0) {
      this.plane.position.y = 0;
      this.plane.rotation.z = 0;
    } else {
      const B_abs = Math.abs(this.bend);
      const R = (H * H + B_abs * B_abs) / (2 * B_abs);
      const effectiveX = Math.min(Math.abs(x), H);

      const arc = R - Math.sqrt(R * R - effectiveX * effectiveX);
      if (this.bend > 0) {
        this.plane.position.y = -arc;
        this.plane.rotation.z = -Math.sign(x) * Math.asin(effectiveX / R);
      } else {
        this.plane.position.y = arc;
        this.plane.rotation.z = Math.sign(x) * Math.asin(effectiveX / R);
      }
    }

    this.speed = scroll.current - scroll.last;
    this.program.uniforms.uTime.value += 0.04;
    this.program.uniforms.uSpeed.value = this.speed;

    const planeOffset = this.plane.scale.x / 2;
    const viewportOffset = this.viewport.width / 2;
    this.isBefore = this.plane.position.x + planeOffset < -viewportOffset;
    this.isAfter = this.plane.position.x - planeOffset > viewportOffset;
    if (direction === 'right' && this.isBefore) {
      this.extra -= this.widthTotal;
      this.isBefore = this.isAfter = false;
    }
    if (direction === 'left' && this.isAfter) {
      this.extra += this.widthTotal;
      this.isBefore = this.isAfter = false;
    }
  }

  onResize({ screen, viewport }: { screen?: { width: number, height: number }; viewport?: { width: number, height: number } } = {}) {
    if (screen) this.screen = screen;
    if (viewport) {
      this.viewport = viewport;
    }
    
    // 限定单次最大显示 5 个元素，分配每个卡片占据的 3D 空间宽度
    const visibleCount = 5;
    this.width = this.viewport.width / visibleCount;
    
    // 设置两侧留白间距 (10%)
    this.padding = this.width * 0.1;
    this.plane.scale.x = this.width - this.padding;
    
    // 专门为竖直 (约 16:9/竖拍) 规格修改的自适应高度计算：允许其高度达到宽度的 1.5倍 填满更多竖向空间
    // 并且预留出 30% 底部空间给标签文本和圆弧弯折下坠
    this.plane.scale.y = Math.min(this.plane.scale.x * 1.5, this.viewport.height * 0.70);
    
    this.plane.program.uniforms.uPlaneSizes.value = [this.plane.scale.x, this.plane.scale.y];
    
    // 重要修复：因为 title.mesh 是 plane 的子节点，会【二次继承】 plane 的巨幅 scale。
    // 如果直接把世界坐标差距塞给子节点，文字将被缩放无数倍并掉出画面。我们必须用目标世界坐标除以父级的 scale 转换为 local scale。
    if (this.title && this.title.mesh) {
      // 1. 对于长图，文字在世界中的高度相对于卡片不应该太大，我们期望一个绝对的较小比例
      const desiredWorldHeight = this.plane.scale.y * 0.15;
      const desiredWorldWidth = desiredWorldHeight * this.title.aspect;
      
      // 2. 抵消父节点缩放的影响，反向除以父节点比例以达到所期待的世界视觉宽/高
      this.title.mesh.scale.set(
        desiredWorldWidth / this.plane.scale.x,
        desiredWorldHeight / this.plane.scale.y,
        1
      );
      
      // 3. 将位置定在主界面的底部 (local Y = -0.5)，再加上文字一半占据的 local height 和外边距 0.08 的 local offset
      this.title.mesh.position.y = -0.5 - (desiredWorldHeight * 0.5 + 0.08) / this.plane.scale.y;
    }

    this.widthTotal = this.width * this.length;
    this.x = this.width * this.index;
  }
}

interface AppConfig {
  items?: { image: string; text: string; value?: string }[];
  bend?: number;
  textColor?: string;
  borderRadius?: number;
  font?: string;
  scrollSpeed?: number;
  scrollEase?: number;
  onSelect: (text: string) => void;
}

class App {
  container: HTMLElement;
  scrollSpeed: number;
  scroll: {
    ease: number;
    current: number;
    target: number;
    last: number;
    position?: number;
  };
  onCheckDebounce: (...args: any[]) => void;
  renderer!: Renderer;
  gl!: GL;
  camera!: Camera;
  scene!: Transform;
  planeGeometry!: Plane;
  medias: Media[] = [];
  mediasImages: { image: string; text: string; value?: string }[] = [];
  screen!: { width: number; height: number };
  viewport!: { width: number; height: number };
  raf: number = 0;

  isDown: boolean = false;
  start: number = 0;
  moved: boolean = false;
  startTime: number = 0;
  onSelectCallback: (text: string) => void;

  constructor(
    container: HTMLElement,
    {
      items,
      bend = 1,
      textColor = '#ffffff',
      borderRadius = 0,
      font = 'bold 30px Figtree',
      scrollSpeed = 2,
      scrollEase = 0.05,
      onSelect
    }: AppConfig
  ) {
    autoBind(this);
    this.container = container;
    this.scrollSpeed = scrollSpeed;
    this.scroll = { ease: scrollEase, current: 0, target: 0, last: 0 };
    this.onCheckDebounce = debounce(this.onCheck, 200);
    this.onSelectCallback = onSelect;
    this.createRenderer();
    this.createCamera();
    this.createScene();
    this.onResize();
    this.createGeometry();
    this.createMedias(items, bend, textColor, borderRadius, font);
    this.update();
    this.addEventListeners();
  }

  createRenderer() {
    this.renderer = new Renderer({ alpha: true });
    this.gl = this.renderer.gl;
    this.gl.clearColor(0, 0, 0, 0);
    this.container.appendChild(this.renderer.gl.canvas as HTMLCanvasElement);
  }

  createCamera() {
    this.camera = new Camera(this.gl);
    this.camera.fov = 45;
    this.camera.position.z = 20;
  }

  createScene() {
    this.scene = new Transform();
  }

  createGeometry() {
    this.planeGeometry = new Plane(this.gl, {
      heightSegments: 50,
      widthSegments: 100
    });
  }

  createMedias(
    items: { image: string; text: string; value?: string }[] | undefined,
    bend: number = 1,
    textColor: string,
    borderRadius: number,
    font: string
  ) {
    const defaultItems: { image: string; text: string; value?: string }[] = [];
    const galleryItems = (items && items.length) ? items : defaultItems;
    this.mediasImages = galleryItems.concat(galleryItems);
    this.medias = this.mediasImages.map((data, index) => {
      return new Media({
        geometry: this.planeGeometry,
        gl: this.gl,
        image: data.image,
        index,
        length: this.mediasImages.length,
        renderer: this.renderer,
        scene: this.scene,
        screen: this.screen,
        text: data.text,
        value: data.value,
        viewport: this.viewport,
        bend,
        textColor,
        borderRadius,
        font
      });
    });
  }

  onTouchDown(e: any) {
    this.isDown = true;
    this.moved = false;
    this.startTime = Date.now();
    this.scroll.position = this.scroll.current;
    this.start = e.touches ? e.touches[0].clientX : e.clientX;
  }

  onTouchMove(e: any) {
    if (!this.isDown) return;
    const x = e.touches ? e.touches[0].clientX : e.clientX;
    const distance = (this.start - x) * (this.scrollSpeed * 0.025);
    if (Math.abs(distance) > 0.01) {
      this.moved = true;
    }
    this.scroll.target = (this.scroll.position ?? 0) + distance;
  }

  onTouchUp(e: any) {
    this.isDown = false;
    
    let clickedIndexOffset = 0;
    let validClick = false;
    
    if (!this.moved && (Date.now() - this.startTime < 200) && e) {
      const x = e.type === 'touchend' ? e.changedTouches[0].clientX : e.clientX;
      if (x !== undefined) {
        // 利用 getBoundingClientRect 因为容器可能在屏幕居中但并未铺满
        const rect = this.container.getBoundingClientRect();
        const relativeX = x - rect.left;
        const centerOffset = relativeX - (this.screen.width / 2);
        const itemPixels = this.screen.width / 5; // 取决于 onResize() 中写死的 visibleCount = 5
        clickedIndexOffset = Math.round(centerOffset / itemPixels);
        validClick = true;
      }
    }

    if (validClick && this.medias && this.medias[0]) {
      const width = this.medias[0].width;
      const centerScrollIndex = Math.round(this.scroll.target / width);
      const targetIndex = centerScrollIndex + clickedIndexOffset;
      
      // 滑动并将画廊居中被点击元素
      this.scroll.target = targetIndex * width;
      
      const normalizedIndex = ((targetIndex % this.mediasImages.length) + this.mediasImages.length) % this.mediasImages.length;
      const selectedItem = this.mediasImages[normalizedIndex];
      if (selectedItem) {
        this.onSelectCallback(selectedItem.value || selectedItem.text);
      }
    } else {
      this.onCheck();
    }
  }

  onWheel(e: any) {
    const delta = e.deltaY ?? e.wheelDelta ?? e.detail ?? 0;
    this.scroll.target += delta > 0 ? this.scrollSpeed : -this.scrollSpeed;
    this.onCheckDebounce();
  }

  onCheck() {
    if (!this.medias || !this.medias[0]) return;
    const width = this.medias[0].width;
    const itemIndex = Math.round(Math.abs(this.scroll.target) / width);
    const item = width * itemIndex;
    this.scroll.target = this.scroll.target < 0 ? -item : item;
  }

  onResize() {
    this.screen = {
      width: this.container.clientWidth,
      height: this.container.clientHeight
    };
    this.renderer.setSize(this.screen.width, this.screen.height);
    this.camera.perspective({
      aspect: this.screen.width / this.screen.height
    });
    const fov = (this.camera.fov * Math.PI) / 180;
    const height = 2 * Math.tan(fov / 2) * this.camera.position.z;
    const width = height * this.camera.aspect;
    this.viewport = { width, height };
    
    // 专门为 bend 属性服务：把整个 3D 舞台向上平移屏幕高度的 8%，
    // 这样在 bend=3 让边缘卡片向下弯折坠落时，依然能稳稳地在容器范围内展示它的名字，不被 CSS overflow 砍断
    if (this.scene) {
      this.scene.position.y = height * 0.08;
    }

    if (this.medias) {
      this.medias.forEach(media => media.onResize({ screen: this.screen, viewport: this.viewport }));
    }
  }

  update() {
    this.scroll.current = lerp(this.scroll.current, this.scroll.target, this.scroll.ease);
    const direction = this.scroll.current > this.scroll.last ? 'right' : 'left';
    if (this.medias) {
      this.medias.forEach(media => media.update(this.scroll, direction));
    }
    this.renderer.render({ scene: this.scene, camera: this.camera });
    this.scroll.last = this.scroll.current;
    this.raf = window.requestAnimationFrame(this.update);
  }

  addEventListeners() {
    window.addEventListener('resize', this.onResize);
    this.container.addEventListener('wheel', this.onWheel);
    this.container.addEventListener('mousedown', this.onTouchDown);
    this.container.addEventListener('touchstart', this.onTouchDown);
    window.addEventListener('mousemove', this.onTouchMove);
    window.addEventListener('mouseup', this.onTouchUp);
    window.addEventListener('touchmove', this.onTouchMove);
    window.addEventListener('touchend', this.onTouchUp);
  }

  destroy() {
    window.cancelAnimationFrame(this.raf);
    window.removeEventListener('resize', this.onResize);
    window.removeEventListener('mousemove', this.onTouchMove);
    window.removeEventListener('mouseup', this.onTouchUp);
    window.removeEventListener('touchmove', this.onTouchMove);
    window.removeEventListener('touchend', this.onTouchUp);
    this.container.removeEventListener('wheel', this.onWheel);
    this.container.removeEventListener('mousedown', this.onTouchDown);
    this.container.removeEventListener('touchstart', this.onTouchDown);
    if (this.renderer && this.renderer.gl && this.renderer.gl.canvas.parentNode) {
      this.renderer.gl.canvas.parentNode.removeChild(this.renderer.gl.canvas as HTMLCanvasElement);
    }
  }
}

onMounted(() => {
  if (!containerRef.value) return;

  app = new App(containerRef.value, {
    items: props.items,
    bend: props.bend,
    textColor: props.textColor,
    borderRadius: props.borderRadius,
    font: props.font,
    scrollSpeed: props.scrollSpeed,
    scrollEase: props.scrollEase,
    onSelect: (val: string) => emit('select', val)
  });
});

onUnmounted(() => {
  if (app) {
    app.destroy();
    app = null;
  }
});

watch(
  () => ({
    items: props.items,
    bend: props.bend,
    textColor: props.textColor,
    borderRadius: props.borderRadius,
    font: props.font,
    scrollSpeed: props.scrollSpeed,
    scrollEase: props.scrollEase
  }),
  newProps => {
    if (app) {
      app.destroy();
    }
    if (containerRef.value) {
      app = new App(containerRef.value, { ...newProps, onSelect: (val: string) => emit('select', val) });
    }
  },
  { deep: true }
);
</script>
