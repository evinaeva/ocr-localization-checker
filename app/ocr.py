from google.cloud import vision


def process_image(image_bytes: bytes) -> str:
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=image_bytes)
    response = client.text_detection(image=image)

    if response.error.message:
        # В проде — логировать; для новичка — вернуть текст ошибки
        return f"Vision API error: {response.error.message}"

    if not response.text_annotations:
        return "No text detected."

    return response.text_annotations[0].description
