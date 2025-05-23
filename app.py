"""
Viseme Generation API
--------------------------------
API để tạo lip sync cho nhân vật 2D từ audio và văn bản tiếng Việt hoặc tiếng Anh.
Sử dụng Montreal Forced Aligner (MFA) để phân đoạn audio thành phoneme,
sau đó chuyển đổi phoneme sang viseme.

Hướng dẫn sử dụng:
1. Cài đặt môi trường và các thư viện cần thiết theo README.md
2. Cài đặt Montreal Forced Aligner và model vietnamese_mfa và english_us_arpa
3. Chạy API với uvicorn app:app --host 0.0.0.0 --port 8000
4. Gửi request POST với audio và transcript tới /api/generate-viseme
"""

import os
import json
import time
import uuid
import tempfile
import subprocess
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime

import asyncio
import aiofiles
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends, BackgroundTasks, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("./logs/api.log")
    ]
)
logger = logging.getLogger(__name__)

# Khởi tạo FastAPI app
app = FastAPI(
    title="Viseme Generation API",
    description="API tạo lip sync cho nhân vật 2D từ audio và văn bản tiếng Việt hoặc tiếng Anh",
    version="2.0.0",
)

# Cấu hình CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cho phép tất cả origin trong môi trường dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates configuration
templates = Jinja2Templates(directory="templates")

# Cấu hình đường dẫn
BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = Path(tempfile.gettempdir()) / "viseme_api"
TEMP_DIR.mkdir(exist_ok=True)
UPLOAD_DIR = TEMP_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
RESULTS_DIR = TEMP_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# Đường dẫn đến tệp mapping phoneme sang viseme
VIETNAMESE_PHONEME_TO_VISEME_MAP_PATH = BASE_DIR / "data/vietnamese-phoneme-to-viseme.json"
ENGLISH_PHONEME_TO_VISEME_MAP_PATH = BASE_DIR / "data/english-phoneme-to-viseme.json"

# Đường dẫn tới MFA và model
MFA_CMD = "mfa"  # Đảm bảo MFA đã được cài đặt và có trong PATH

# Cấu hình model cho từng ngôn ngữ
LANGUAGE_MODELS = {
    "vi": {
        "acoustic_model": "vietnamese_mfa",
        "dictionary": "vietnamese_mfa"
    },
    "en": {
        "acoustic_model": "english_us_arpa",
        "dictionary": "english_us_arpa"
    }
}

# Load mapping phoneme sang viseme cho tiếng Việt
try:
    with open(VIETNAMESE_PHONEME_TO_VISEME_MAP_PATH, "r", encoding="utf-8") as f:
        vietnamese_phoneme_to_viseme_data = json.load(f)
        VIETNAMESE_PHONEME_TO_VISEME_MAP = vietnamese_phoneme_to_viseme_data["phonemeToViseme"]
    logger.info(f"Loaded Vietnamese phoneme to viseme mapping from {VIETNAMESE_PHONEME_TO_VISEME_MAP_PATH}")
except Exception as e:
    logger.error(f"Error loading Vietnamese phoneme to viseme mapping: {e}")
    raise

# Load mapping phoneme sang viseme cho tiếng Anh
try:
    with open(ENGLISH_PHONEME_TO_VISEME_MAP_PATH, "r", encoding="utf-8") as f:
        english_phoneme_to_viseme_data = json.load(f)
        ENGLISH_PHONEME_TO_VISEME_MAP = english_phoneme_to_viseme_data["phonemeToViseme"]
    logger.info(f"Loaded English phoneme to viseme mapping from {ENGLISH_PHONEME_TO_VISEME_MAP_PATH}")
except Exception as e:
    logger.error(f"Error loading English phoneme to viseme mapping: {e}")
    raise

# Models
class VisemeGenerationRequest(BaseModel):
    transcript: str = Field(..., description="Văn bản cần tạo lip sync")
    language: str = Field("vi", description="Ngôn ngữ (vi: Tiếng Việt, en: Tiếng Anh)")

class VisemeGenerationResponse(BaseModel):
    request_id: str = Field(..., description="ID của request")
    processing_time: float = Field(..., description="Thời gian xử lý (giây)")
    status: str = Field(..., description="Trạng thái xử lý")
    viseme_timeline: List[Dict[str, Any]] = Field(..., description="Timeline của các viseme")
    transcript: str = Field(..., description="Văn bản đã xử lý")
    language: str = Field(..., description="Ngôn ngữ được sử dụng")
    metadata: Dict[str, Any] = Field(..., description="Metadata của quá trình xử lý")

class ErrorResponse(BaseModel):
    error: str = Field(..., description="Mô tả lỗi")
    details: Optional[str] = Field(None, description="Chi tiết lỗi (nếu có)")

# Hàm tiện ích
def generate_unique_id():
    """Tạo ID duy nhất cho mỗi request"""
    return str(uuid.uuid4())

def cleanup_temp_files(file_paths: List[Path]):
    """Xóa các tệp tạm thời sau khi xử lý xong"""
    for file_path in file_paths:
        try:
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted temporary file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to delete temporary file {file_path}: {e}")

def create_lab_file(transcript: str, output_path: Path) -> Path:
    """Tạo tệp .lab từ văn bản cho MFA"""
    # Chuẩn hóa văn bản (xóa ký tự đặc biệt, chuyển về chữ thường)
    normalized_transcript = transcript.lower()
    
    # Ghi văn bản vào tệp .txt
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(normalized_transcript)
    
    logger.info(f"Created lab file at {output_path}")
    return output_path

async def run_mfa_align(audio_path: Path, transcript_path: Path, output_path: Path, language: str) -> bool:
    """Chạy Montreal Forced Aligner để tạo alignment"""
    start_time = time.time()
    logger.info(f"Starting MFA alignment for {language}: {audio_path} with {transcript_path}")
    
    # Lấy model phù hợp với ngôn ngữ
    if language not in LANGUAGE_MODELS:
        logger.error(f"Unsupported language: {language}")
        return False
    
    acoustic_model = LANGUAGE_MODELS[language]["acoustic_model"]
    dictionary = LANGUAGE_MODELS[language]["dictionary"]
    
    cmd = [
        MFA_CMD, "align_one",
        str(audio_path), str(transcript_path),
        acoustic_model, dictionary,
        str(output_path),
        "--output_format", "json",
        "--single_speaker",
        "--use_mp",
        "--num_jobs", "8",
        "--clean",
        "--final_clean",
        "--overwrite",
        "--textgrid_cleanup"
    ]
    
    try:
        # Chạy MFA trong một process riêng
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"MFA alignment failed with code {process.returncode}")
            logger.error(f"MFA stderr: {stderr.decode()}")
            return False
        
        logger.info(f"MFA alignment completed in {time.time() - start_time:.2f}s")
        return True
    
    except Exception as e:
        logger.error(f"Error running MFA: {e}")
        return False

def map_phoneme_to_viseme(phoneme: str, language: str) -> int:
    """Chuyển đổi phoneme sang viseme sử dụng bảng mapping"""
    # Chọn bảng mapping dựa trên ngôn ngữ
    if language == "vi":
        phoneme_to_viseme_map = VIETNAMESE_PHONEME_TO_VISEME_MAP
        
        # Xử lý đặc biệt cho phoneme tiếng Việt
        if phoneme in phoneme_to_viseme_map:
            return phoneme_to_viseme_map[phoneme]
        
        # Nếu không tìm thấy, thử loại bỏ các ký tự đánh dấu thanh điệu và độ dài
        import re
        simplified_phoneme = re.sub(r'[ː˦˥˨ˀ˦˨˩ˀ˩˦˩˨̚ʷw͡]', '', phoneme)
        
        if simplified_phoneme in phoneme_to_viseme_map:
            return phoneme_to_viseme_map[simplified_phoneme]
    elif language == "en":
        phoneme_to_viseme_map = ENGLISH_PHONEME_TO_VISEME_MAP
        
        # Xử lý phoneme tiếng Anh
        if phoneme in phoneme_to_viseme_map:
            return phoneme_to_viseme_map[phoneme]
    
    # Nếu vẫn không tìm thấy, trả về viseme mặc định (0 - Rest)
    logger.warning(f"No viseme mapping found for phoneme: {phoneme} in {language}, using default 0")
    return 0

def convert_mfa_json_to_viseme_timeline(mfa_json_path: Path, language: str) -> List[Dict[str, Any]]:
    """Chuyển đổi kết quả JSON từ MFA thành timeline viseme"""
    try:
        with open(mfa_json_path, "r", encoding="utf-8") as f:
            mfa_data = json.load(f)
        
        if not mfa_data or "tiers" not in mfa_data or "phones" not in mfa_data["tiers"] or "entries" not in mfa_data["tiers"]["phones"]:
            logger.error(f"Invalid MFA JSON format in {mfa_json_path}")
            raise ValueError("Invalid MFA JSON format")
        
        phone_entries = mfa_data["tiers"]["phones"]["entries"]
        viseme_timeline = []
        
        for entry in phone_entries:
            start_time = entry[0]
            end_time = entry[1]
            phoneme = entry[2]
            
            viseme = map_phoneme_to_viseme(phoneme, language)
            
            viseme_timeline.append({
                "start": start_time,
                "end": end_time,
                "duration": end_time - start_time,
                "phoneme": phoneme,
                "viseme": viseme
            })
        
        return viseme_timeline
    
    except Exception as e:
        logger.error(f"Error converting MFA JSON to viseme timeline: {e}")
        raise

# API endpoints
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Root endpoint với giao diện web"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/health")
async def health_check():
    """Endpoint kiểm tra sức khỏe của API"""
    # Kiểm tra xem các thành phần cần thiết có hoạt động không
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "api": "ok",
            "temp_directories": "ok"
        }
    }
    
    # Kiểm tra MFA có trong path không
    try:
        process = await asyncio.create_subprocess_exec(
            MFA_CMD, "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode == 0:
            health_status["components"]["mfa"] = "ok"
            health_status["components"]["mfa_version"] = stdout.decode().strip()
        else:
            health_status["components"]["mfa"] = "error"
            health_status["status"] = "degraded"
    except Exception:
        health_status["components"]["mfa"] = "error"
        health_status["status"] = "degraded"
    
    # Kiểm tra mapping files
    if VIETNAMESE_PHONEME_TO_VISEME_MAP_PATH.exists():
        health_status["components"]["vietnamese_viseme_mapping"] = "ok"
    else:
        health_status["components"]["vietnamese_viseme_mapping"] = "error"
        health_status["status"] = "degraded"
    
    if ENGLISH_PHONEME_TO_VISEME_MAP_PATH.exists():
        health_status["components"]["english_viseme_mapping"] = "ok"
    else:
        health_status["components"]["english_viseme_mapping"] = "error"
        health_status["status"] = "degraded"
    
    # Kiểm tra các model MFA
    health_status["components"]["models"] = {}
    for lang, models in LANGUAGE_MODELS.items():
        try:
            # Kiểm tra acoustic model
            process_acoustic = await asyncio.create_subprocess_exec(
                MFA_CMD, "model", "inspect", "acoustic", models["acoustic_model"],
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout_acoustic, stderr_acoustic = await process_acoustic.communicate()
            
            # Kiểm tra dictionary
            process_dict = await asyncio.create_subprocess_exec(
                MFA_CMD, "model", "inspect", "dictionary", models["dictionary"],
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout_dict, stderr_dict = await process_dict.communicate()
            
            if process_acoustic.returncode == 0 and process_dict.returncode == 0:
                health_status["components"]["models"][lang] = "ok"
            else:
                health_status["components"]["models"][lang] = "error"
                health_status["status"] = "degraded"
        except Exception:
            health_status["components"]["models"][lang] = "error"
            health_status["status"] = "degraded"
    
    return health_status

# Thêm import
from fastapi.responses import FileResponse

# Thêm vào API của bạn
@app.get("/api/examples/{language}")
async def get_example(language: str):
    """Endpoint để lấy dữ liệu ví dụ cho từng ngôn ngữ"""
    if language not in ["vi", "en"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language: {language}. Supported languages: vi, en"
        )
    
    # Đường dẫn đến thư mục ví dụ
    examples_dir = BASE_DIR / "static/examples"
    
    # Đọc nội dung tệp text
    try:
        with open(examples_dir / f"example_{language}.txt", "r", encoding="utf-8") as f:
            text = f.read().strip()
    except Exception as e:
        logger.error(f"Error reading example text for {language}: {e}")
        text = ""
    
    # Trả về dữ liệu ví dụ
    return {
        "text": text,
        "audio_path": f"/static/examples/example_{language}.wav"
    }

# Hoặc có thể trả về file audio trực tiếp
@app.get("/api/examples/{language}/audio")
async def get_example_audio(language: str):
    """Endpoint để lấy file audio ví dụ"""
    if language not in ["vi", "en"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language: {language}. Supported languages: vi, en"
        )
    
    # Đường dẫn đến file audio
    audio_path = BASE_DIR / f"static/examples/example_{language}.wav"
    
    if not audio_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Example audio for {language} not found"
        )
    
    return FileResponse(audio_path)

@app.post("/api/generate-viseme", response_model=VisemeGenerationResponse)
async def generate_viseme(
    background_tasks: BackgroundTasks,
    audio_file: UploadFile = File(..., description="Tệp audio WAV"),
    transcript: str = Form(..., description="Văn bản cần xử lý"),
    language: str = Form("vi", description="Ngôn ngữ (vi: Tiếng Việt, en: Tiếng Anh)"),
):
    """
    Endpoint chính để tạo viseme từ audio và văn bản
    
    - Upload tệp audio WAV
    - Cung cấp văn bản transcript tương ứng
    - Chọn ngôn ngữ (vi hoặc en)
    - Nhận kết quả là timeline các viseme phù hợp với audio
    """
    if language not in LANGUAGE_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language: {language}. Supported languages: {', '.join(LANGUAGE_MODELS.keys())}"
        )
    
    start_time = time.time()
    request_id = generate_unique_id()
    logger.info(f"Request {request_id}: Processing viseme generation for {language}")
    
    # Tạo đường dẫn cho các tệp
    audio_path = UPLOAD_DIR / f"{request_id}_audio.wav"
    transcript_path = UPLOAD_DIR / f"{request_id}_transcript.txt"
    mfa_output_path = RESULTS_DIR / f"{request_id}_alignment.json"
    
    temp_files = [audio_path, transcript_path, mfa_output_path]
    
    try:
        # Lưu tệp audio
        async with aiofiles.open(audio_path, 'wb') as out_file:
            content = await audio_file.read()
            await out_file.write(content)
        logger.info(f"Request {request_id}: Saved audio file to {audio_path}")
        
        # Tạo tệp transcript
        create_lab_file(transcript, transcript_path)
        
        # Chạy MFA để tạo alignment
        mfa_success = await run_mfa_align(audio_path, transcript_path, mfa_output_path, language)
        
        if not mfa_success:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate alignment with Montreal Forced Aligner for {language}"
            )
        
        # Chuyển đổi kết quả MFA thành viseme timeline
        viseme_timeline = convert_mfa_json_to_viseme_timeline(mfa_output_path, language)
        
        # Tính thống kê về viseme
        viseme_counts = {}
        total_duration = 0
        for item in viseme_timeline:
            viseme = item["viseme"]
            duration = item["duration"]
            total_duration += duration
            viseme_counts[str(viseme)] = viseme_counts.get(str(viseme), 0) + 1
        
        # Chuẩn bị response
        processing_time = time.time() - start_time
        response = {
            "request_id": request_id,
            "processing_time": processing_time,
            "status": "success",
            "viseme_timeline": viseme_timeline,
            "transcript": transcript,
            "language": language,
            "metadata": {
                "audio_filename": audio_file.filename,
                "total_duration": total_duration,
                "viseme_statistics": {
                    "counts": viseme_counts,
                    "total_visemes": len(viseme_timeline)
                },
                "process_timestamp": datetime.now().isoformat()
            }
        }
        
        # Thêm task xóa tệp tạm thời
        background_tasks.add_task(cleanup_temp_files, temp_files)
        
        logger.info(f"Request {request_id}: Completed in {processing_time:.2f}s with {len(viseme_timeline)} visemes")
        return response
    
    except Exception as e:
        logger.error(f"Request {request_id}: Error - {str(e)}")
        # Xóa tệp tạm thời nếu có lỗi
        background_tasks.add_task(cleanup_temp_files, temp_files)
        raise HTTPException(
            status_code=500,
            detail=f"Error generating viseme: {str(e)}"
        )

# Xử lý lỗi
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "details": str(exc)}
    )

# Entry point
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)