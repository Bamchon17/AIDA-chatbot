/**
 * Simplified Live2D manager for AIDA chatbot.
 * Handles loading a single model and playing motions by emotion name.
 */

import { CubismFramework, Option } from "@framework/live2dcubismframework";
import { LogLevel } from "@framework/live2dcubismframework";
import { CubismModelSettingJson } from "@framework/cubismmodelsettingjson";
import { ICubismModelSetting } from "@framework/icubismmodelsetting";
import { CubismUserModel } from "@framework/model/cubismusermodel";
import { CubismMoc } from "@framework/model/cubismmoc";
import { CubismPhysics } from "@framework/physics/cubismphysics";
import { CubismMatrix44 } from "@framework/math/cubismmatrix44";
import { CubismMotion } from "@framework/motion/cubismmotion";
import { ACubismMotion, FinishedMotionCallback } from "@framework/motion/acubismmotion";
import { CubismMotionQueueEntryHandle } from "@framework/motion/cubismmotionqueuemanager";
import { CubismRenderer_WebGL } from "@framework/rendering/cubismrenderer_webgl";
import { CubismEyeBlink } from "@framework/effect/cubismeyeblink";
import { BreathParameterData, CubismBreath } from "@framework/effect/cubismbreath";
import { csmVector } from "@framework/type/csmvector";
import { csmMap } from "@framework/type/csmmap";
import { CubismDefaultParameterId } from "@framework/cubismdefaultparameterid";
import { CubismIdHandle } from "@framework/id/cubismid";

export type EmotionType = "Normal" | "Talking" | "Curious";

const MODEL_DIR = "/model/";
const MODEL_FILE = "final5.model3.json";

let _cubismInitialized = false;

function initializeCubism() {
  if (_cubismInitialized) return;
  const cubismOption: Option = {
    logFunction: console.log,
    loggingLevel: LogLevel.LogLevel_Off,
  };
  CubismFramework.startUp(cubismOption);
  CubismFramework.initialize();
  _cubismInitialized = true;
}

export class AidaLive2DModel extends CubismUserModel {
  private _modelSetting: ICubismModelSetting | null = null;
  private _gl: WebGLRenderingContext | null = null;
  private _canvas: HTMLCanvasElement | null = null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private _frameBuffer: any = null;
  private _projectionMatrix: CubismMatrix44 = new CubismMatrix44();
  private _motions: Map<string, CubismMotion> = new Map();
  private _loaded = false;

  public async load(
    gl: WebGLRenderingContext,
    canvas: HTMLCanvasElement,
    frameBuffer: WebGLFramebuffer
  ): Promise<void> {
    this._gl = gl;
    this._canvas = canvas;
    this._frameBuffer = frameBuffer;

    // Fetch model settings
    const settingBuffer = await fetch(MODEL_DIR + MODEL_FILE).then((r) =>
      r.arrayBuffer()
    );
    const setting = new CubismModelSettingJson(
      settingBuffer,
      settingBuffer.byteLength
    );
    this._modelSetting = setting;

    // Load MOC
    const mocPath = MODEL_DIR + setting.getModelFileName();
    const mocBuffer = await fetch(mocPath).then((r) => r.arrayBuffer());
    this.loadModel(mocBuffer, false);

    // Setup renderer
    this.createRenderer();
    const renderer = this.getRenderer() as CubismRenderer_WebGL;
    renderer.initialize(this.getModel());
    renderer.startUp(gl);
    renderer.setIsPremultipliedAlpha(true);

    // Load textures
    const texCount = setting.getTextureCount();
    for (let i = 0; i < texCount; i++) {
      const texPath = MODEL_DIR + setting.getTextureFileName(i);
      await this._loadTexture(texPath, i);
    }

    // Load physics
    const physicsPath = setting.getPhysicsFileName();
    if (physicsPath) {
      const physicsBuffer = await fetch(MODEL_DIR + physicsPath).then((r) =>
        r.arrayBuffer()
      );
      this.loadPhysics(physicsBuffer, physicsBuffer.byteLength);
    }

    // Setup eye blink
    if (setting.getEyeBlinkParameterCount() > 0) {
      this._eyeBlink = CubismEyeBlink.create(setting);
    }

    // Setup breath
    const breathParameters = new csmVector<BreathParameterData>();
    const idManager = CubismFramework.getIdManager();
    breathParameters.pushBack(
      new BreathParameterData(
        idManager.getId(CubismDefaultParameterId.ParamAngleX),
        0.0,
        15.0,
        6.5345,
        0.5
      )
    );
    breathParameters.pushBack(
      new BreathParameterData(
        idManager.getId(CubismDefaultParameterId.ParamAngleY),
        0.0,
        8.0,
        3.5345,
        0.5
      )
    );
    breathParameters.pushBack(
      new BreathParameterData(
        idManager.getId(CubismDefaultParameterId.ParamAngleZ),
        0.0,
        10.0,
        5.5345,
        0.5
      )
    );
    breathParameters.pushBack(
      new BreathParameterData(
        idManager.getId(CubismDefaultParameterId.ParamBodyAngleX),
        0.0,
        4.0,
        15.5345,
        0.5
      )
    );
    breathParameters.pushBack(
      new BreathParameterData(
        idManager.getId(CubismDefaultParameterId.ParamBreath),
        0.5,
        0.5,
        3.2345,
        1.0
      )
    );
    this._breath = CubismBreath.create();
    this._breath.setParameters(breathParameters);

    // Build eye blink and lip sync ID vectors for setEffectIds
    const eyeBlinkIds = new csmVector<CubismIdHandle>();
    for (let i = 0; i < setting.getEyeBlinkParameterCount(); i++) {
      eyeBlinkIds.pushBack(setting.getEyeBlinkParameterId(i));
    }
    const lipSyncIds = new csmVector<CubismIdHandle>();
    for (let i = 0; i < setting.getLipSyncParameterCount(); i++) {
      lipSyncIds.pushBack(setting.getLipSyncParameterId(i));
    }

    // Preload all motions
    const motionGroups = ["Normal", "Talking", "Curious"];
    for (const group of motionGroups) {
      const count = setting.getMotionCount(group);
      for (let i = 0; i < count; i++) {
        const motionPath = MODEL_DIR + setting.getMotionFileName(group, i);
        const motionBuffer = await fetch(motionPath).then((r) => r.arrayBuffer());
        const motion = this.loadMotion(
          motionBuffer,
          motionBuffer.byteLength,
          `${group}_${i}`,
          undefined,
          undefined,
          setting,
          group,
          i
        ) as CubismMotion;
        if (motion) {
          motion.setEffectIds(eyeBlinkIds, lipSyncIds);
          this._motions.set(`${group}_${i}`, motion);
        }
      }
    }

    this._loaded = true;
  }

  public isLoaded(): boolean {
    return this._loaded;
  }

  public stopMotion(): void {
    this._motionManager.stopAllMotions();
  }

  public playMotion(emotion: EmotionType, loop = true): void {
    const key = `${emotion}_0`;
    const motion = this._motions.get(key);
    if (!motion) return;

    // หยุด motion เก่าทันที ไม่ให้ทับกัน
    this._motionManager.stopAllMotions();

    // fade in เบาๆ, fade out เร็ว ป้องกัน overlap
    motion.setFadeInTime(0.3);
    motion.setFadeOutTime(0.0);

    motion.setIsLoop(loop);
    this._motionManager.startMotionPriority(motion, false, 2);
  }

  public update(deltaTime: number): void {
    if (!this._loaded || !this._gl || !this._canvas) return;

    const { width, height } = this._canvas;
    const gl = this._gl;

    // Update time
    this._dragManager.update(deltaTime);
    const dx = this._dragManager.getX();
    const dy = this._dragManager.getY();

    // Update model
    this.getModel().loadParameters();

    if (!this._motionManager.isFinished()) {
      this._motionManager.updateMotion(this.getModel(), deltaTime);
    }

    this.getModel().saveParameters();

    // Eye blink
    if (this._eyeBlink) {
      this._eyeBlink.updateParameters(this.getModel(), deltaTime);
    }

    // Expression (none here)

    // Drag / face tracking
    const idManager = CubismFramework.getIdManager();
    this.getModel().addParameterValueById(
      idManager.getId(CubismDefaultParameterId.ParamAngleX),
      dx * 30
    );
    this.getModel().addParameterValueById(
      idManager.getId(CubismDefaultParameterId.ParamAngleY),
      dy * 30
    );
    this.getModel().addParameterValueById(
      idManager.getId(CubismDefaultParameterId.ParamAngleZ),
      dx * dy * -30
    );
    this.getModel().addParameterValueById(
      idManager.getId(CubismDefaultParameterId.ParamBodyAngleX),
      dx * 10
    );

    // Breath
    if (this._breath) {
      this._breath.updateParameters(this.getModel(), deltaTime);
    }

    // Physics
    if (this._physics) {
      this._physics.evaluate(this.getModel(), deltaTime);
    }

    this.getModel().update();

    // Projection — scale ให้โมเดลใหญ่และ Y ให้ข้อศอกพอดีล่าง
    this._projectionMatrix.loadIdentity();
    const scale = 2.2;          // ปรับตัวเลขนี้เพื่อเปลี่ยนขนาด (ใหญ่ขึ้น = มากขึ้น)
    const offsetY = -0.25;      // เลื่อนลงให้เห็นข้อศอก (ลบ = ลง)

    this.getModelMatrix().setWidth(2.0);
    this._projectionMatrix.scale(
      scale * (height / width),
      scale
    );
    this._projectionMatrix.translateY(offsetY);
    this.getModelMatrix().setupFromLayout(new csmMap<string, number>());

    const renderer = this.getRenderer() as CubismRenderer_WebGL;
    renderer.setMvpMatrix(this._projectionMatrix);
    renderer.setRenderState(this._frameBuffer, [0, 0, width, height]);
    renderer.drawModel();
  }

  public release(): void {
    this._motions.clear();
    this.deleteRenderer();
  }

  private async _loadTexture(
    path: string,
    index: number
  ): Promise<void> {
    return new Promise((resolve) => {
      const img = new Image();
      img.onload = () => {
        const gl = this._gl!;
        const tex = gl.createTexture()!;
        gl.bindTexture(gl.TEXTURE_2D, tex);
        gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
        gl.bindTexture(gl.TEXTURE_2D, null);
        const renderer = this.getRenderer() as CubismRenderer_WebGL;
        renderer.bindTexture(index, tex);
        resolve();
      };
      img.onerror = () => resolve();
      img.src = path;
    });
  }

  // Required by CubismUserModel but we handle it differently
  public reloadRenderer(): void {
    this.deleteRenderer();
    this.createRenderer();
    const renderer = this.getRenderer() as CubismRenderer_WebGL;
    renderer.initialize(this.getModel());
    renderer.startUp(this._gl!);
  }
}

export class Live2DManager {
  private _gl: WebGLRenderingContext | null = null;
  private _canvas: HTMLCanvasElement | null = null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private _frameBuffer: any = null;
  private _model: AidaLive2DModel | null = null;
  private _animFrameId: number | null = null;
  private _lastTime = 0;
  private _currentEmotion: EmotionType | null = null;

  public async initialize(canvas: HTMLCanvasElement): Promise<boolean> {
    initializeCubism();

    const gl = canvas.getContext("webgl", {
      alpha: true,
      premultipliedAlpha: true,
    });
    if (!gl) {
      console.error("[Live2D] WebGL not supported");
      return false;
    }

    this._gl = gl;
    this._canvas = canvas;
    this._frameBuffer = gl.getParameter(gl.FRAMEBUFFER_BINDING);

    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    gl.disable(gl.DEPTH_TEST);

    const model = new AidaLive2DModel();
    await model.load(gl, canvas, this._frameBuffer);
    this._model = model;

    this._lastTime = performance.now();
    this._startLoop();
    return true;
  }

  public stopMotion(): void {
    this._currentEmotion = null;
    this._model?.stopMotion();
  }

  public setEmotion(emotion: EmotionType): void {
    if (this._currentEmotion === emotion) return;
    this._currentEmotion = emotion;
    this._model?.playMotion(emotion);
  }

  public release(): void {
    if (this._animFrameId !== null) {
      cancelAnimationFrame(this._animFrameId);
      this._animFrameId = null;
    }
    this._model?.release();
    this._model = null;
    if (_cubismInitialized) {
      CubismFramework.dispose();
      _cubismInitialized = false;
    }
  }

  private _startLoop(): void {
    const loop = (time: number) => {
      const delta = (time - this._lastTime) / 1000;
      this._lastTime = time;

      const gl = this._gl!;
      const canvas = this._canvas!;

      gl.clearColor(0.0, 0.0, 0.0, 0.0);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);

      if (this._model?.isLoaded()) {
        this._model.update(delta);
      }

      this._animFrameId = requestAnimationFrame(loop);
    };
    this._animFrameId = requestAnimationFrame(loop);
  }
}
