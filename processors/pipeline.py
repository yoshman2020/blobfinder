from .registry import get_processor


def apply_pipeline(image, pipeline):
    current = image
    blobs = None
    for step in pipeline:
        processor = get_processor(step.type)
        try:
            result = processor(
                current, step.params, islast=step == pipeline[-1]
            )
        except Exception as e:
            raise RuntimeError(f"{step.type} failed: {e}")
        if isinstance(result, tuple):
            current, blobs = result
        else:
            current = result
            blobs = None
    return current, blobs
