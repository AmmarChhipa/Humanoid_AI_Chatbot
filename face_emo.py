from deepface import DeepFace
import cv2S

# Start the webcam
cap = cv2.VideoCapture(1)

if not cap.isOpened():
    print("Error: Could not open webcam.")
    exit()

while True:
    ret, frame = cap.read()
    if not ret:
        print("Error: Failed to capture frame.")
        break

    try:
        # Analyze the frame for emotions
        results = DeepFace.analyze(
            frame,
            actions=['emotion'],
            enforce_detection=False,  # Set to False to avoid breaking on undetected faces
            detector_backend='opencv'  # Faster backend for real-time
        )

        if results:
            emotion = results[0]['dominant_emotion']
            region = results[0].get('region', {})
            x = region.get('x', 50)
            y = region.get('y', 50)
            w = region.get('w', 100)
            h = region.get('h', 100)

            # Draw rectangle around face
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

            # Draw the emotion
            cv2.putText(frame, f"{emotion}", (x, y - 10 if y - 10 > 10 else y + 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    except Exception as e:
        print("Warning:", e)

    # Show the live frame
    cv2.imshow("Real-Time Emotion Detection", frame)

    # Break the loop with 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Clean up
cap.release()
cv2.destroyAllWindows()
