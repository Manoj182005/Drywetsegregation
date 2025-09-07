import cv2
from inference_sdk import InferenceHTTPClient
from flask import Flask, render_template, Response, jsonify, request
import os
import uuid
import time  # Added for potential retry logic

app = Flask(__name__)

# Configure DroidCam URL
VIDEO_URL = "http://10.48.165.249:4747/video"

# Configure Roboflow API
CLIENT = InferenceHTTPClient(
    api_url="https://serverless.roboflow.com",
    api_key="N0cC31lVxB1dRk08Cc3S"
)

# Updated model ID
MODEL_ID = "dry-wet-object-detection-qxxpa/2"

# Ensure static and uploads directories exist
UPLOAD_FOLDER = 'static/uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists('static'):
    os.makedirs('static')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Global variables for DroidCam (auto) detection
latest_auto_classification = "unknown"
latest_auto_predictions = []

# Global variables for manual upload detection
latest_manual_image_path = None
latest_manual_predictions = []

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Helper function for inference and drawing
def process_image_for_inference(image_path):
    img = cv2.imread(image_path)
    if img is None:
        return None, "Error: Could not read image."

    # Perform inference (using Roboflow API)
    result = CLIENT.infer(image_path, model_id=MODEL_ID)
    predictions = result.get("predictions", [])

    # Draw predictions on the image
    for p in predictions:
        x1 = int(p['x'] - p['width'] / 2)
        y1 = int(p['y'] - p['height'] / 2)
        x2 = int(p['x'] + p['width'] / 2)
        y2 = int(p['y'] + p['height'] / 2)

        color = (0, 255, 0)  # Green in BGR format
        thickness = 2
        cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)

        label = f"{p['class']} {p['confidence']:.2f}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        cv2.putText(img, label, (x1, y1 - 10), font, font_scale, color, thickness)

    return img, predictions

# Routes
@app.route('/')
def index():
    return render_template('index.html')

# DroidCam (Auto-detection) Status
@app.route('/auto_status')
def auto_status():
    global latest_auto_classification, latest_auto_predictions
    image_path = 'static/temp.jpg'
    image_url = image_path + '?' + str(os.path.getmtime(image_path)) if os.path.exists(image_path) else ''
    return jsonify({
        'image_url': image_url,
        'classification': latest_auto_classification,
        'predictions': latest_auto_predictions
    })

# DroidCam (Auto-detection) Classification
@app.route('/classify', methods=['GET'])
def classify():
    global latest_auto_classification, latest_auto_predictions

    # Capture frame from DroidCam with retry logic
    cap = cv2.VideoCapture(VIDEO_URL)
    for _ in range(3):  # Retry up to 3 times
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                break
        time.sleep(1)  # Wait 1 second before retrying
    else:
        print("Error: Could not open DroidCam stream after retries.")
        cap.release()
        return Response("Error: Could not open DroidCam stream.", status=500)

    cap.release()
    if not ret:
        print("Error: Failed to capture frame.")
        return Response("Error: Failed to capture frame.", status=500)

    # Save frame for inference
    temp_original_path = os.path.join(app.config['UPLOAD_FOLDER'], "temp_auto_original.jpg")
    cv2.imwrite(temp_original_path, frame)
    if not os.path.exists(temp_original_path):
        print("Error: Failed to save temporary image.")
        return Response("Error: Failed to save temporary image.", status=500)

    # Process image with Roboflow
    annotated_img, predictions = process_image_for_inference(temp_original_path)
    if annotated_img is None:
        print("Error: Image processing failed.")
        return Response("Error processing DroidCam image.", status=500)

    # Save annotated image
    auto_image_display_path = "static/temp.jpg"
    cv2.imwrite(auto_image_display_path, annotated_img)

    # Store predictions
    latest_auto_predictions = predictions
    print("Predictions:", predictions)  # Debug output

    # Determine classification
    classification_result = "unknown"
    if predictions:
        top_prediction = max(predictions, key=lambda p: p["confidence"])
        detected_class = top_prediction["class"].lower()
        print("Top class:", detected_class)  # Debug output
        # Handle various possible class names
        if any(keyword in detected_class for keyword in ["dry", "dryobject", "dry_object","d"]):
            classification_result = "dry"
        elif any(keyword in detected_class for keyword in ["wet", "wetobject", "wet_object","w"]):
            classification_result = "wet"
    
    latest_auto_classification = classification_result
    print("Classification result:", classification_result)  # Debug output

    return Response(classification_result, mimetype='text/plain')

# Manual Image Upload Route
@app.route('/upload', methods=['POST'])
def upload_file():
    global latest_manual_image_path, latest_manual_predictions

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        filename = str(uuid.uuid4()) + os.path.splitext(file.filename)[1]
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        annotated_img, predictions = process_image_for_inference(filepath)
        if annotated_img is None:
            return jsonify({'error': 'Error processing uploaded image.'}), 500

        manual_display_path = os.path.join(app.config['UPLOAD_FOLDER'], "manual_temp.jpg")
        cv2.imwrite(manual_display_path, annotated_img)

        latest_manual_image_path = 'static/uploads/manual_temp.jpg'
        latest_manual_predictions = predictions

        return jsonify({
            'success': True,
            'image_url': latest_manual_image_path,
            'predictions': predictions
        })
    else:
        return jsonify({'error': 'File type not allowed'}), 400

# Manual Image Status
@app.route('/manual_status')
def manual_status():
    global latest_manual_image_path, latest_manual_predictions
    image_url = latest_manual_image_path + '?' + str(os.path.getmtime(os.path.join('static/uploads', 'manual_temp.jpg'))) if latest_manual_image_path and os.path.exists(os.path.join('static/uploads', 'manual_temp.jpg')) else ''
    return jsonify({
        'image_url': image_url,
        'predictions': latest_manual_predictions
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)