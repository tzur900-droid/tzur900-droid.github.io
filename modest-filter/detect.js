// טעינת המודלים (רצים מקומית בדפדפן, בלי אינטרנט ובלי עלות) והרצתם על פריים.
import { PoseLandmarker, FaceDetector } from "./lib/vision_bundle.mjs";

const base = new URL(".", import.meta.url).href;
const fileset = {
  wasmLoaderPath: base + "lib/wasm/vision_wasm_internal.js",
  wasmBinaryPath: base + "lib/wasm/vision_wasm_internal.wasm"
};

let pose, face, nsfw, lastTs = 0;

async function create(Cls, opts) {
  for (const delegate of ["GPU", "CPU"]) {
    try {
      return await Cls.createFromOptions(fileset, { ...opts, baseOptions: { ...opts.baseOptions, delegate } });
    } catch (e) {
      if (delegate === "CPU") throw e;
      console.warn("GPU לא זמין, עובר ל-CPU", e);
    }
  }
}

export async function load(onProgress) {
  onProgress?.("טוען זיהוי גוף...");
  pose = await create(PoseLandmarker, {
    baseOptions: { modelAssetPath: base + "models/pose_landmarker_lite.task" },
    runningMode: "VIDEO", numPoses: 5,
    minPoseDetectionConfidence: 0.35, minPosePresenceConfidence: 0.35, minTrackingConfidence: 0.35
  });
  onProgress?.("טוען זיהוי פנים...");
  face = await create(FaceDetector, {
    baseOptions: { modelAssetPath: base + "models/face_detector.tflite" },
    runningMode: "VIDEO", minDetectionConfidence: 0.5
  });
  onProgress?.("טוען זיהוי סצנות...");
  const tf = globalThis.tf;
  await tf.setBackend("webgl").catch(() => tf.setBackend("cpu"));
  await tf.ready();
  nsfw = await tf.loadLayersModel(base + "models/nsfw/model.json");
  tf.tidy(() => nsfw.predict(tf.zeros([1, 224, 224, 3])));
}

// canvas: הפריים בגודל עבודה. מחזיר אנשים, פרצופים והסתברויות לסצנה.
export function analyze(canvas, withScene) {
  const ts = Math.max(performance.now(), lastTs + 1);
  lastTs = ts;
  const p = pose.detectForVideo(canvas, ts);
  const f = face.detectForVideo(canvas, ts);
  const W = canvas.width, H = canvas.height;
  const faces = (f.detections || []).map((d) => {
    const b = d.boundingBox;
    return { cx: (b.originX + b.width / 2) / W, cy: (b.originY + b.height / 2) / H, w: b.width / W };
  });
  let scene = null;
  if (withScene) {
    const tf = globalThis.tf;
    const probs = tf.tidy(() => {
      const img = tf.browser.fromPixels(canvas).toFloat().div(255);
      const x = tf.image.resizeBilinear(img, [224, 224], true).reshape([1, 224, 224, 3]);
      return nsfw.predict(x).dataSync();
    });
    scene = { drawing: probs[0], hentai: probs[1], neutral: probs[2], porn: probs[3], sexy: probs[4] };
  }
  return { people: (p.landmarks || []).map((lm) => ({ lm })), faces, scene };
}
