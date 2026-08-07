import cv2

def generate_augmentations(img):
    """
    Generate slightly modified versions of the image
    to test prediction stability.
    """

    return [
        ("original", img),

        ("flip", cv2.flip(img, 1)),

        ("bright",
         cv2.convertScaleAbs(img, alpha=1.2, beta=20)),

        ("dark",
         cv2.convertScaleAbs(img, alpha=0.8, beta=-20)),

        ("rotate",
         cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE))
    ]