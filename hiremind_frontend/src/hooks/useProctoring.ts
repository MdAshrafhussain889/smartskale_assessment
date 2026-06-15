"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

type FaceDetectorCtor = new (options?: {
  fastMode?: boolean;
  maxDetectedFaces?: number;
}) => {
  detect(source: HTMLVideoElement | HTMLCanvasElement): Promise<
    {
      boundingBox?: DOMRectReadOnly;
      landmarks?: { type?: string; locations?: { x: number; y: number }[] }[];
    }[]
  >;
};

declare global {
  interface Window {
    FaceDetector?: FaceDetectorCtor;
  }
}

export interface ProctoringState {
  cameraReady: boolean;
  detectorReady: boolean;
  faceCount: number | null;
  eyeSignal: "ok" | "missing" | "unsupported";
  lastEvent: string | null;
  error: string | null;
}

const emptyState: ProctoringState = {
  cameraReady: false,
  detectorReady: false,
  faceCount: null,
  eyeSignal: "unsupported",
  lastEvent: null,
  error: null,
};

export function useProctoring(
  enabled: boolean,
  attemptId: string,
  token: string,
) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const lastLoggedRef = useRef<Record<string, number>>({});
  const [state, setState] = useState<ProctoringState>(emptyState);

  const captureSnapshot = useCallback(() => {
    const video = videoRef.current;
    if (!video || !video.videoWidth || !video.videoHeight) return undefined;

    const canvas = canvasRef.current ?? document.createElement("canvas");
    canvasRef.current = canvas;
    canvas.width = 360;
    canvas.height = Math.round((video.videoHeight / video.videoWidth) * canvas.width);
    const ctx = canvas.getContext("2d");
    if (!ctx) return undefined;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", 0.62);
  }, []);

  const logEvent = useCallback(
    async (eventType: string, metadata?: Record<string, unknown>, includeSnapshot = true) => {
      if (!enabled || !attemptId || !token) return;

      const key = `${eventType}:${metadata?.signal ?? ""}`;
      const now = Date.now();
      if (now - (lastLoggedRef.current[key] ?? 0) < 8000) return;
      lastLoggedRef.current[key] = now;

      try {
        await api.logProctorEvent(token, {
          session_id: attemptId,
          event_type: eventType,
          timestamp: new Date().toISOString(),
          metadata,
          frame_snapshot: includeSnapshot ? captureSnapshot() : undefined,
        });
        setState((prev) => ({ ...prev, lastEvent: eventType }));
      } catch {
        // Proctoring must never block the assessment.
      }
    },
    [attemptId, captureSnapshot, enabled, token],
  );

  useEffect(() => {
    if (!enabled || !attemptId || !token) return;

    let cancelled = false;
    let scanTimer: ReturnType<typeof setInterval> | undefined;
    let snapshotTimer: ReturnType<typeof setInterval> | undefined;

    async function startCamera() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
          audio: false,
        });
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play().catch(() => undefined);
        }

        const detector = window.FaceDetector
          ? new window.FaceDetector({ fastMode: true, maxDetectedFaces: 3 })
          : null;

        setState((prev) => ({
          ...prev,
          cameraReady: true,
          detectorReady: Boolean(detector),
          error: detector ? null : "Face detection is not supported in this browser.",
        }));

        if (detector) {
          scanTimer = setInterval(async () => {
            const video = videoRef.current;
            if (!video || video.readyState < 2) return;
            try {
              const faces = await detector.detect(video);
              const faceCount = faces.length;
              const landmarks = faces[0]?.landmarks ?? [];
              const hasEyeLandmark = landmarks.some((item) =>
                String(item.type ?? "").toLowerCase().includes("eye"),
              );

              setState((prev) => ({
                ...prev,
                faceCount,
                eyeSignal: hasEyeLandmark ? "ok" : "missing",
              }));

              if (faceCount === 0) {
                logEvent("face_missing", { signal: "face_detection", face_count: 0 });
              } else if (faceCount > 1) {
                logEvent("multi_face", { signal: "face_detection", face_count: faceCount });
              } else if (!hasEyeLandmark) {
                logEvent("other", { signal: "eye_tracking", detail: "eye landmarks unavailable" });
              }
            } catch {
              setState((prev) => ({
                ...prev,
                detectorReady: false,
                error: "Face detector stopped responding.",
              }));
            }
          }, 3500);
        }

        snapshotTimer = setInterval(() => {
          logEvent("other", { signal: "snapshot", detail: "periodic webcam snapshot" });
        }, 30000);
      } catch {
        setState((prev) => ({ ...prev, error: "Camera permission was denied or unavailable." }));
        logEvent("face_missing", { signal: "camera", detail: "camera unavailable" }, false);
      }
    }

    function onVisibility() {
      if (document.hidden) {
        logEvent("tab_switch", { signal: "visibility" });
      }
    }

    function onFullscreen() {
      if (!document.fullscreenElement) {
        logEvent("fullscreen_exit", { signal: "fullscreen" });
      }
    }

    function onCopy(e: ClipboardEvent) {
      e.preventDefault();
      logEvent("copy_paste", { signal: "clipboard" });
    }

    document.addEventListener("visibilitychange", onVisibility);
    document.addEventListener("fullscreenchange", onFullscreen);
    document.addEventListener("copy", onCopy);
    document.documentElement.requestFullscreen?.().catch(() => undefined);
    startCamera();

    return () => {
      cancelled = true;
      document.removeEventListener("visibilitychange", onVisibility);
      document.removeEventListener("fullscreenchange", onFullscreen);
      document.removeEventListener("copy", onCopy);
      if (scanTimer) clearInterval(scanTimer);
      if (snapshotTimer) clearInterval(snapshotTimer);
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    };
  }, [attemptId, enabled, logEvent, token]);

  return { videoRef, state };
}
