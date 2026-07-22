"""
run_video_test.py

DEMO / TEST SCRIPT -- reads an uploaded video file frame by frame, runs the
trained YOLO model on each frame through ppe_vision_adapter, evaluates PPE
compliance for each frame through ppe_compliance_service (the same pure
logic worker_safety_agent uses), and reports results continuously:

  - a live annotated preview window (boxes + running compliance status)
  - a line printed to the console for every processed frame
  - an annotated .mp4 written to disk so you can review it afterwards
  - a final summary (average compliance score, how often each item was
    missing, timestamps of the worst frames)

This does NOT go through Kafka / the agent runner -- it calls
evaluate_ppe_compliance() directly, which is the same compliance function
worker_safety_agent.py uses internally. That's enough to prove "does my
trained model correctly detect PPE across a real video", which is the
question this script answers. Wiring this into the full event-bus pipeline
is a separate step (see run_pipeline_demo.py for that shape).

USAGE:
    python run_video_test.py \
        --video /path/to/uploaded_video.mp4 \
        --weights /path/to/best.pt \
        --required helmet,vest,gloves \
        --output annotated_output.mp4

    Press "q" in the preview window to stop early. If you're running
    headless (no display), pass --no-display and just watch the console /
    read the output video afterwards.
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "worker_safety_agent"))

import cv2

from ppe_vision_adapter import UltralyticsYOLODetector
from ppe_compliance_service import evaluate_ppe_compliance

BOX_COLOR_OK = (0, 200, 0)      # green, BGR
BOX_COLOR_MISSING = (0, 0, 220)  # red, BGR
TEXT_COLOR = (255, 255, 255)


def draw_overlay(frame, detections, compliance) -> None:
    for d in detections:
        x1, y1, x2, y2 = map(int, d.bbox_xyxy)
        is_negative = d.class_name.startswith("no-")
        color = BOX_COLOR_MISSING if is_negative else BOX_COLOR_OK
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, f"{d.class_name} {d.confidence:.2f}", (x1, max(0, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)

    status_text = (
        f"compliance={compliance.ppe_compliance_score:.2f}  "
        f"violations={compliance.ppe_violations or 'none'}"
    )
    banner_color = BOX_COLOR_OK if compliance.is_fully_compliant else BOX_COLOR_MISSING
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 28), banner_color, -1)
    cv2.putText(frame, status_text, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, TEXT_COLOR, 1, cv2.LINE_AA)


def main() -> int:
    parser = argparse.ArgumentParser(description="Continuous PPE detection test over an uploaded video.")
    parser.add_argument("--video", required=True, help="Path to the uploaded video file")
    parser.add_argument("--weights", required=True, help="Path to trained YOLO weights (e.g. best.pt)")
    parser.add_argument("--required", default="helmet,vest,gloves",
                         help="Comma-separated list of required PPE items for this test (default: helmet,vest,gloves)")
    parser.add_argument("--worker-id", default="W-TEST-1")
    parser.add_argument("--zone-id", default="Z-TEST")
    parser.add_argument("--confidence", type=float, default=0.5)
    parser.add_argument("--imgsz", type=int, default=640,
                         help="Inference resolution. Increase for wide/crowd shots with small objects "
                              "(e.g. helmets far from camera) -- try 1280. Slower but sees more detail.")
    parser.add_argument("--sample-every", type=int, default=1,
                         help="Run inference on every Nth frame (default 1 = every frame). "
                              "Increase this if the video is long / inference is slow.")
    parser.add_argument("--output", default="annotated_output.mp4", help="Path to write the annotated video")
    parser.add_argument("--no-display", action="store_true", help="Don't open a live preview window")
    args = parser.parse_args()

    required_ppe = [item.strip() for item in args.required.split(",") if item.strip()]

    video_path = Path(args.video)
    if not video_path.exists():
        print(f"ERROR: video not found at {video_path}")
        return 1

    weights_path = Path(args.weights)
    if not weights_path.exists():
        print(f"ERROR: weights file not found at {weights_path}")
        return 1

    print(f"Loading model from {weights_path} ...")
    detector = UltralyticsYOLODetector(weights_path=str(weights_path), confidence_threshold=args.confidence, imgsz=args.imgsz)
    print(f"Model classes: {detector._model.names}")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"ERROR: could not open video {video_path}")
        return 1

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    writer = cv2.VideoWriter(args.output, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))

    frame_index = 0
    processed_count = 0
    scores: list[float] = []
    violation_counter: Counter[str] = Counter()
    worst_frames: list[tuple[float, int]] = []  # (score, frame_index)
    start_time = time.time()

    print(f"Video: {width}x{height} @ {fps:.1f}fps, {total_frames} frames total")
    print(f"Required PPE for this test: {required_ppe}")
    print("Processing... (press q in preview window to stop early)\n")

    last_detections = []
    last_compliance = None

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        run_inference = (frame_index % args.sample_every == 0)

        if run_inference:
            detections = detector.predict_frame(frame)
            ppe_status = {}
            for item in required_ppe:
                positive = any(d.class_name == item and d.confidence >= args.confidence for d in detections)
                ppe_status[item] = positive
            # also fold in explicit negative classes for anything named "no-<item>"
            for d in detections:
                if d.class_name.startswith("no-"):
                    item = d.class_name[3:]
                    if item in required_ppe:
                        ppe_status[item] = False

            compliance = evaluate_ppe_compliance(
                worker_id=args.worker_id, zone_id=args.zone_id,
                detected_ppe=ppe_status, required_ppe=required_ppe,
            )

            last_detections, last_compliance = detections, compliance
            processed_count += 1
            scores.append(compliance.ppe_compliance_score)
            for v in compliance.ppe_violations:
                violation_counter[v] += 1
            worst_frames.append((compliance.ppe_compliance_score, frame_index))

            timestamp_s = frame_index / fps
            print(f"[frame {frame_index:>6} | t={timestamp_s:6.2f}s] "
                  f"score={compliance.ppe_compliance_score:.2f} "
                  f"violations={compliance.ppe_violations or 'none'}")

        if last_compliance is not None:
            draw_overlay(frame, last_detections, last_compliance)

        writer.write(frame)

        if not args.no_display:
            cv2.imshow("PPE detection test", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                print("\nStopped early by user.")
                break

        frame_index += 1

    elapsed = time.time() - start_time
    cap.release()
    writer.release()
    if not args.no_display:
        cv2.destroyAllWindows()

    print("\n--- SUMMARY ---")
    print(f"Frames processed: {processed_count} / {frame_index} total read, in {elapsed:.1f}s "
          f"({processed_count / elapsed:.1f} inferences/sec)" if elapsed > 0 else "")
    if scores:
        print(f"Average compliance score: {sum(scores) / len(scores):.3f}")
        print(f"Fully compliant frames: {sum(1 for s in scores if s == 1.0)} / {len(scores)}")
        print("Violation frequency by item:")
        for item, count in violation_counter.most_common():
            print(f"  {item}: missing in {count}/{len(scores)} frames ({100 * count / len(scores):.1f}%)")
        worst_frames.sort(key=lambda pair: pair[0])
        print("Worst 5 frames (lowest compliance score):")
        for score, idx in worst_frames[:5]:
            print(f"  frame {idx} (t={idx / fps:.2f}s): score={score:.2f}")
    else:
        print("No frames were processed.")
    print(f"\nAnnotated video written to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())