# BigModel API Capabilities for Aily Chaos

## Research Summary

Based on official documentation and SDK references, here are the multimodal APIs available on BigModel (Zhipu AI) platform.

---

## 1. Vision Models (GLM-4V Series)

### Available Models

| Model | Parameters | Context | Best For | Cost |
|-------|-----------|---------|----------|------|
| **GLM-5.1** | - | 128K | General text + code | Standard |
| **GLM-4.6V** | 106B (12B active) | 128K | Production vision tasks | Paid |
| **GLM-4.6V-Flash** | ~9B | 128K | Fast inference, FREE | **Free** |
| **GLM-4.1V-Thinking** | - | 128K | Vision + reasoning | Paid |
| **GLM-4V-Flash** | - | 128K | Basic vision | Free |

### Capabilities
- **Image understanding**: Scene analysis, object recognition, text in images
- **Multi-image**: Can process multiple images in one request
- **Long context**: ~300 pages or 1-hour video equivalent
- **Function calling**: Native tool use with vision (GLM-4.6V)
- **Screenshots to code**: Design2Code benchmark 93.4%

### API Format (OpenAI Compatible)

```python
from zhipuai import ZhipuAI
import base64

client = ZhipuAI(api_key="your-key")

# Encode image to base64
with open("image.jpg", "rb") as f:
    base64_image = base64.b64encode(f.read()).decode('utf-8')

# Call vision API
response = client.chat.completions.create(
    model="glm-4v",  # or glm-4.6v-flash
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "Describe this image"},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }
            }
        ]
    }],
    max_tokens=1024
)
```

**Endpoint:** `https://open.bigmodel.cn/api/paas/v4/chat/completions`

---

## 2. OCR Model (GLM-OCR)

### Capabilities
- **Document parsing**: PDFs, images, PowerPoints
- **Layout preservation**: Tables, formulas, headings
- **Output format**: Markdown with structure
- **Page range**: Can specify start/end pages
- **Max**: 100 pages, 50MB per file

### API Format

```python
import requests

# Method 1: Using file URL
response = requests.post(
    "https://api.z.ai/api/paas/v4/layout_parsing",
    headers={
        "Authorization": "Bearer YOUR_KEY",
        "Content-Type": "application/json"
    },
    json={
        "model": "glm-ocr",
        "file": "https://example.com/document.pdf"
    }
)

# Method 2: Using base64
response = requests.post(
    "https://api.z.ai/api/paas/v4/layout_parsing",
    headers={
        "Authorization": "Bearer YOUR_KEY",
        "Content-Type": "application/json"
    },
    json={
        "model": "glm-ocr",
        "file": f"data:application/pdf;base64,{base64_pdf}",
        "start_page_id": 1,
        "end_page_id": 10
    }
)

result = response.json()
# Returns: text (markdown), layout_details, etc.
```

**Endpoint:** `https://api.z.ai/api/paas/v4/layout_parsing`

### Performance
- **Speed**: 1.86 pages/second (PDF)
- **Cost**: ~0.2 RMB per million tokens (~1 RMB for 2000 A4 pages)
- **Accuracy**: SOTA on OmniDocBench v1.5

---

## 3. Speech Recognition (GLM-ASR)

### Available Models
- **GLM-ASR-2512**: Latest ASR model
- **GLM-4-Voice**: Voice interaction model
- **GLM-Realtime**: Real-time audio/video

### Capabilities
- **Multilingual**: Chinese, English, and others
- **Streaming**: Real-time transcription
- **Audio formats**: MP3, WAV, M4A, etc.
- **Long audio**: Supports hours-long files

### API Format

```python
import requests

response = requests.post(
    "https://open.bigmodel.cn/api/paas/v4/audio/transcriptions",
    headers={"Authorization": "Bearer YOUR_KEY"},
    files={"file": open("audio.mp3", "rb")},
    data={
        "model": "glm-asr-2512",
        "language": "zh",  # or "en", "auto"
        "response_format": "json"
    }
)

result = response.json()
# Returns: text, segments with timestamps
```

---

## 4. Real-time Multimodal (GLM-Realtime)

### Capabilities
- **Real-time voice conversation**
- **Video understanding**: Live video stream analysis
- **Low latency**: Streaming responses

### Use Cases
- Live meeting transcription with video context
- Real-time presentation assistance
- Interactive video analysis

---

## 5. Embedding Models

### Available Models
- **Embedding-2**: Standard embeddings
- **Embedding-3**: Latest version

### Specs
- **Dimensions**: 1024
- **Max tokens**: 512
- **Use case**: RAG, similarity search

---

## Integration Matrix for Aily Chaos

| Content Type | Primary API | Fallback | Notes |
|-------------|-------------|----------|-------|
| **PDF** | GLM-OCR | GLM-4V | OCR for layout, 4V for complex figures |
| **Images** | GLM-4V / GLM-4.6V-Flash | EasyOCR | Vision for understanding, OCR for text |
| **Video** | GLM-ASR + GLM-4V frames | Whisper | Audio transcript + key frame analysis |
| **Audio** | GLM-ASR | Whisper | Native API preferred |
| **PPTX** | GLM-OCR | python-pptx | OCR handles layout better |
| **Screenshots** | GLM-4V | - | UI analysis, code generation |
| **Scanned Docs** | GLM-OCR | Tesseract | Layout preservation critical |

---

## Cost Optimization Strategy

### Free Tier
- **GLM-4.6V-Flash**: Vision tasks (limited time)
- **GLM-4V-Flash**: Basic vision
- **GLM-OCR**: Very low cost (~1 RMB/2000 pages)

### Cost-Effective Pipeline
1. **Text extraction**: GLM-OCR (cheapest for documents)
2. **Visual understanding**: GLM-4.6V-Flash (free tier)
3. **Complex reasoning**: GLM-5.1 (text) or GLM-4.1V-Thinking (vision)

### Rate Limits
- Typical: 3-10 requests/second
- Can request increase for enterprise

---

## Python SDK Installation

```bash
# Official SDK (recommended)
pip install zhipuai

# Alternative SDK
pip install zai-sdk

# OCR CLI tool
pip install glmocr
```

---

## Authentication

Get API Key: https://bigmodel.cn/usercenter/proj-mgmt/apikeys

```python
from zhipuai import ZhipuAI

client = ZhipuAI(api_key="your-api-key")

# Or using environment variable
import os
client = ZhipuAI(api_key=os.getenv("BIGMODEL_API_KEY"))
```

---

## References

1. [Official BigModel Docs](https://docs.bigmodel.cn/)
2. [GLM-OCR GitHub](https://github.com/zai-org/GLM-OCR)
3. [Model Overview](https://docs.bigmodel.cn/cn/guide/start/model-overview)
4. [GLM-4.6V Paper](https://arxiv.org/abs/2412.07753)
5. [GLM-OCR Paper](https://arxiv.org/html/2603.10910v1)
