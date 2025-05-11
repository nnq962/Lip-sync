from gtts import gTTS
import os
import argparse
import subprocess
from pydub import AudioSegment

def text_to_speech(text, output_file, lang='vi', output_format='mp3', english_voice=False):
    """
    Chuyển văn bản thành giọng nói và lưu theo định dạng mong muốn
    
    Args:
        text (str): Văn bản cần chuyển thành giọng nói
        output_file (str): Tên tệp đầu ra (không bao gồm phần mở rộng)
        lang (str): Mã ngôn ngữ (mặc định: 'vi' cho tiếng Việt)
        output_format (str): Định dạng đầu ra ('mp3' hoặc 'wav')
        english_voice (bool): Sử dụng giọng tiếng Anh bất kể ngôn ngữ đầu vào
    """
    # Tạo thư mục data nếu chưa tồn tại
    data_dir = os.path.join(os.getcwd(), 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    # Tạo đường dẫn đầy đủ cho các tệp trong thư mục data
    mp3_file = os.path.join(data_dir, f"{output_file}.mp3")
    txt_file = os.path.join(data_dir, f"{output_file}.txt")
    
    # Nếu tùy chọn giọng tiếng Anh được chọn, ghi đè ngôn ngữ
    if english_voice:
        lang = 'en'
    
    # Tạo giọng nói từ văn bản
    tts = gTTS(text=text, lang=lang)
    
    # Lưu ra tệp mp3
    tts.save(mp3_file)
    
    # Lưu nội dung văn bản
    with open(txt_file, "w", encoding="utf-8") as f:
        f.write(text)
    
    # Nếu định dạng đầu ra là wav, chuyển đổi mp3 sang wav
    if output_format.lower() == 'wav':
        wav_file = os.path.join(data_dir, f"{output_file}.wav")
        
        # Sử dụng pydub để chuyển đổi
        try:
            sound = AudioSegment.from_mp3(mp3_file)
            sound.export(wav_file, format="wav")
            
            # Xóa tệp mp3 trung gian nếu chuyển đổi thành công và định dạng yêu cầu là wav
            os.remove(mp3_file)
            
            print(f"Tệp wav đã được tạo: {wav_file}")
            print(f"Nội dung văn bản được lưu tại: {txt_file}")
            
        except Exception as e:
            print(f"Lỗi khi chuyển đổi sang wav: {e}")
            print(f"Tệp mp3 đã được giữ lại: {mp3_file}")
    else:
        print(f"Tệp mp3 đã được tạo: {mp3_file}")
        print(f"Nội dung văn bản được lưu tại: {txt_file}")

def get_supported_languages():
    """Trả về danh sách các ngôn ngữ được hỗ trợ bởi gTTS"""
    supported_languages = {
        'af': 'Afrikaans',
        'ar': 'Arabic',
        'bn': 'Bengali',
        'bs': 'Bosnian',
        'ca': 'Catalan',
        'cs': 'Czech',
        'cy': 'Welsh',
        'da': 'Danish',
        'de': 'German',
        'el': 'Greek',
        'en': 'English',
        'en-au': 'English (Australia)',
        'en-ca': 'English (Canada)',
        'en-gb': 'English (UK)',
        'en-gh': 'English (Ghana)',
        'en-ie': 'English (Ireland)',
        'en-in': 'English (India)',
        'en-ng': 'English (Nigeria)',
        'en-nz': 'English (New Zealand)',
        'en-ph': 'English (Philippines)',
        'en-tz': 'English (Tanzania)',
        'en-uk': 'English (UK)',
        'en-us': 'English (US)',
        'en-za': 'English (South Africa)',
        'eo': 'Esperanto',
        'es': 'Spanish',
        'es-es': 'Spanish (Spain)',
        'es-us': 'Spanish (United States)',
        'et': 'Estonian',
        'fi': 'Finnish',
        'fr': 'French',
        'fr-ca': 'French (Canada)',
        'fr-fr': 'French (France)',
        'gu': 'Gujarati',
        'hi': 'Hindi',
        'hr': 'Croatian',
        'hu': 'Hungarian',
        'hy': 'Armenian',
        'id': 'Indonesian',
        'is': 'Icelandic',
        'it': 'Italian',
        'ja': 'Japanese',
        'jw': 'Javanese',
        'km': 'Khmer',
        'kn': 'Kannada',
        'ko': 'Korean',
        'la': 'Latin',
        'lv': 'Latvian',
        'mk': 'Macedonian',
        'ml': 'Malayalam',
        'mr': 'Marathi',
        'my': 'Myanmar (Burmese)',
        'ne': 'Nepali',
        'nl': 'Dutch',
        'no': 'Norwegian',
        'pl': 'Polish',
        'pt': 'Portuguese',
        'pt-br': 'Portuguese (Brazil)',
        'pt-pt': 'Portuguese (Portugal)',
        'ro': 'Romanian',
        'ru': 'Russian',
        'si': 'Sinhala',
        'sk': 'Slovak',
        'sq': 'Albanian',
        'sr': 'Serbian',
        'su': 'Sundanese',
        'sv': 'Swedish',
        'sw': 'Swahili',
        'ta': 'Tamil',
        'te': 'Telugu',
        'th': 'Thai',
        'tl': 'Filipino',
        'tr': 'Turkish',
        'uk': 'Ukrainian',
        'ur': 'Urdu',
        'vi': 'Vietnamese',
        'zh-CN': 'Chinese (Simplified)',
        'zh-TW': 'Chinese (Traditional)'
    }
    return supported_languages

if __name__ == "__main__":
    # Lấy danh sách ngôn ngữ được hỗ trợ
    supported_languages = get_supported_languages()
    
    # Tạo trình phân tích tham số dòng lệnh
    parser = argparse.ArgumentParser(description='Chuyển văn bản thành giọng nói')
    parser.add_argument('--text', type=str, help='Văn bản cần chuyển thành giọng nói')
    parser.add_argument('--file', type=str, help='Tệp văn bản đầu vào')
    parser.add_argument('--output', type=str, default='output', help='Tên tệp đầu ra (không bao gồm phần mở rộng)')
    parser.add_argument('--lang', type=str, default='vi', 
                        choices=list(supported_languages.keys()),
                        help=f'Mã ngôn ngữ (mặc định: vi cho tiếng Việt). Sử dụng --list-languages để xem tất cả ngôn ngữ được hỗ trợ.')
    parser.add_argument('--format', type=str, default='mp3', choices=['mp3', 'wav'], 
                        help='Định dạng đầu ra (mp3 hoặc wav, mặc định: mp3)')
    parser.add_argument('--english-voice', action='store_true', 
                        help='Sử dụng giọng tiếng Anh (bất kể ngôn ngữ văn bản)')
    parser.add_argument('--list-languages', action='store_true', 
                        help='Liệt kê tất cả các ngôn ngữ được hỗ trợ')
    
    args = parser.parse_args()
    
    # Hiển thị danh sách ngôn ngữ nếu được yêu cầu
    if args.list_languages:
        print("Danh sách các ngôn ngữ được hỗ trợ:")
        for code, name in sorted(supported_languages.items()):
            print(f"  {code}: {name}")
        exit(0)
    
    # Lấy văn bản từ tham số hoặc tệp
    if args.text:
        input_text = args.text
    elif args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                input_text = f.read()
        except Exception as e:
            print(f"Lỗi khi đọc tệp: {e}")
            exit(1)
    else:
        # Văn bản mặc định nếu không có tham số
        if args.english_voice:
            input_text = "Hello, this is a text converted to English voice."
        else:
            input_text = "Xin chào, đây là đoạn văn bản được chuyển thành giọng nói tiếng Việt."
    
    # Hiển thị thông tin về ngôn ngữ được sử dụng
    if args.english_voice:
        print(f"Đang sử dụng giọng tiếng Anh cho văn bản...")
    else:
        lang_name = supported_languages.get(args.lang, args.lang)
        print(f"Đang sử dụng ngôn ngữ: {lang_name} ({args.lang})")
    
    # Chuyển văn bản thành giọng nói
    text_to_speech(input_text, args.output, args.lang, args.format, args.english_voice)