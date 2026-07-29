import tkinter as tk
from tkinter import ttk, filedialog, messagebox as _orig_messagebox
import subprocess
import os
import sys
import threading
import json
import time
import re
import math
import shutil
import datetime
import random
import tempfile
from pathlib import Path
import urllib.request
import zipfile
import io
import unicodedata
import queue
import uuid
import concurrent.futures

active_app = None


class CustomMessageDialog(tk.Toplevel):
    """[v4.55] 현재 메인 작업창(self.root)의 중앙 좌표를 기준으로 완벽히 정렬되는 커스텀 대화상자"""
    def __init__(self, parent, title, message, icon_type="info", is_ask=False):
        super().__init__(parent)
        self.title(title)
        self.result = False if is_ask else True
        self.transient(parent)
        self.grab_set()

        self.configure(bg="#f4f6f8")

        lines = str(message).split('\n')
        max_line_len = max(len(line) for line in lines) if lines else 20
        w = max(440, min(740, max_line_len * 9 + 100))
        h = max(200, min(580, len(lines) * 22 + 150))

        # 메인 작업창(parent) 중심점 좌표 계산
        try:
            parent.update_idletasks()
            px, py = parent.winfo_x(), parent.winfo_y()
            pw, ph = parent.winfo_width(), parent.winfo_height()
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()

            cx = px + (pw // 2)
            cy = py + (ph // 2)

            x = cx - (w // 2)
            y = cy - (h // 2)

            # 화면 경계 오버플로우 안전 보정 (상하좌우 10~40px)
            x = max(10, min(x, sw - w - 10))
            y = max(10, min(y, sh - h - 40))
        except Exception:
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            x = (sw - w) // 2
            y = (sh - h) // 2

        self.geometry(f"{w}x{h}+{x}+{y}")
        self.resizable(False, False)

        card = ttk.Frame(self, padding=20, style='Card.TFrame')
        card.pack(fill="both", expand=True, padx=8, pady=8)

        icon_map = {
            'info': 'ℹ️',
            'warning': '⚠️',
            'error': '❌',
            'question': '❓'
        }
        icon_str = icon_map.get(icon_type, 'ℹ️')

        hdr_frame = ttk.Frame(card)
        hdr_frame.pack(fill="x", pady=(0, 10))

        lbl_icon = ttk.Label(hdr_frame, text=icon_str, font=("맑은 고딕", 16))
        lbl_icon.pack(side="left", padx=(0, 8))

        lbl_title = ttk.Label(hdr_frame, text=title, font=("맑은 고딕", 11, "bold"))
        lbl_title.pack(side="left", anchor="w")

        lbl_msg = ttk.Label(card, text=message, font=("맑은 고딕", 9), justify="left", wraplength=w - 60)
        lbl_msg.pack(fill="both", expand=True, pady=(0, 15))

        btn_frame = ttk.Frame(card)
        btn_frame.pack(anchor="e")

        if is_ask:
            btn_yes = ttk.Button(btn_frame, text="예 (Yes)", command=self.on_yes, width=11, style='Primary.TButton')
            btn_yes.pack(side="left", padx=(0, 6))
            btn_no = ttk.Button(btn_frame, text="아니오 (No)", command=self.on_no, width=10)
            btn_no.pack(side="left")
            self.bind("<Return>", lambda e: self.on_yes())
            self.bind("<Escape>", lambda e: self.on_no())
            btn_yes.focus_set()
        else:
            btn_ok = ttk.Button(btn_frame, text="확인 (OK)", command=self.on_yes, width=11, style='Primary.TButton')
            btn_ok.pack(side="left")
            self.bind("<Return>", lambda e: self.on_yes())
            self.bind("<Escape>", lambda e: self.on_yes())
            btn_ok.focus_set()

    def on_yes(self):
        self.result = True
        self.destroy()

    def on_no(self):
        self.result = False
        self.destroy()


class AppMessageBox:
    """[v4.55] 메인 작업창 정중앙에 커스텀 대화상자를 배치하는 래퍼 클래스"""
    @staticmethod
    def _resolve_parent(parent=None):
        if parent is not None and hasattr(parent, 'winfo_exists') and parent.winfo_exists():
            return parent
        if 'active_app' in globals() and active_app and hasattr(active_app, 'root'):
            return active_app.root
        return None

    @classmethod
    def showinfo(cls, title, message, parent=None):
        p = cls._resolve_parent(parent)
        if p:
            dlg = CustomMessageDialog(p, title, message, icon_type="info", is_ask=False)
            p.wait_window(dlg)
            return dlg.result
        return _orig_messagebox.showinfo(title, message, parent=parent)

    @classmethod
    def showwarning(cls, title, message, parent=None):
        p = cls._resolve_parent(parent)
        if p:
            dlg = CustomMessageDialog(p, title, message, icon_type="warning", is_ask=False)
            p.wait_window(dlg)
            return dlg.result
        return _orig_messagebox.showwarning(title, message, parent=parent)

    @classmethod
    def showerror(cls, title, message, parent=None):
        p = cls._resolve_parent(parent)
        if p:
            dlg = CustomMessageDialog(p, title, message, icon_type="error", is_ask=False)
            p.wait_window(dlg)
            return dlg.result
        return _orig_messagebox.showerror(title, message, parent=parent)

    @classmethod
    def askyesno(cls, title, message, parent=None):
        p = cls._resolve_parent(parent)
        if p:
            dlg = CustomMessageDialog(p, title, message, icon_type="question", is_ask=True)
            p.wait_window(dlg)
            return dlg.result
        return _orig_messagebox.askyesno(title, message, parent=parent)


messagebox = AppMessageBox

# ------------------------------------------------------------------
# [v3.0] 콘솔 인코딩 안전화: cp949 콘솔에서 한글/특수문자 경로를 print할 때
#  UnicodeEncodeError로 프로그램이 중단되지 않도록 표준 출력을 UTF-8로 재구성한다.
# ------------------------------------------------------------------
for _stream_name in ('stdout', 'stderr'):
    _s = getattr(sys, _stream_name, None)
    try:
        if _s and hasattr(_s, 'reconfigure'):
            _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# tkinterdnd2 라이브러리가 설치되어 있으면 드래그 앤 드롭 활성화
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DND_SUPPORTED = True
except ImportError:
    DND_SUPPORTED = False

# [v3.8] Pillow가 있으면 미리보기 확대/축소를 고품질(LANCZOS)로 처리한다.
try:
    from PIL import Image, ImageTk
    PIL_SUPPORTED = True
except ImportError:
    PIL_SUPPORTED = False


class WidgetToolTip:
    """[v4.60] 위젯 마우스 오버 시 툴팁 팝업 유틸리티"""
    _active_tips = []

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind("<Enter>", self.show_tip)
        widget.bind("<Leave>", self.hide_tip)
        widget.bind("<ButtonPress>", self.hide_tip)  # [v4.631M] 버튼 클릭 시 툴팁 즉시 닫기

    @classmethod
    def hide_all_tips(cls):
        """[v4.631M] 대화상자 오픈 전 활성화된 모든 툴팁 즉시 닫기"""
        for tip in list(cls._active_tips):
            tip.hide_tip()
        cls._active_tips.clear()

    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return
        WidgetToolTip.hide_all_tips()
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        # [v4.63] 화면 경계 밖으로 넘어가지 않도록 보정
        screen_w = self.widget.winfo_screenwidth()
        screen_h = self.widget.winfo_screenheight()
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.attributes('-topmost', True)
        label = tk.Label(tw, text=self.text, justify='left',
                         bg="#1e293b", fg="#f8fafc", relief='solid', borderwidth=1,
                         font=("맑은 고딕", 9), padx=10, pady=6,
                         wraplength=min(520, screen_w - 80))
        label.pack(ipadx=1)
        tw.update_idletasks()
        tw_w = tw.winfo_reqwidth()
        tw_h = tw.winfo_reqheight()
        if x + tw_w > screen_w - 10:
            x = screen_w - tw_w - 10
        if y + tw_h > screen_h - 40:
            y = self.widget.winfo_rooty() - tw_h - 4
        tw.wm_geometry(f"+{x}+{y}")
        if self not in WidgetToolTip._active_tips:
            WidgetToolTip._active_tips.append(self)

    def hide_tip(self, event=None):
        tw = self.tip_window
        self.tip_window = None
        if self in WidgetToolTip._active_tips:
            WidgetToolTip._active_tips.remove(self)
        if tw:
            try:
                tw.destroy()
            except Exception:
                pass


class CustomResolutionDialog(tk.Toplevel):
    """[v4.55] 해상도 가로(X축) / 세로(Y축) 분리 팝업 대화상자"""
    def __init__(self, parent, prev_w="1920", prev_h="1080"):
        super().__init__(parent)
        self.title("📐 해상도 직접 입력")
        self.result = None
        self.transient(parent)
        self.grab_set()

        w, h = 380, 200
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w = min(w, sw - 40)
        h = min(h, sh - 60)

        # 현재 메인 창의 중앙 위치를 기준으로 정렬
        try:
            parent.update_idletasks()
            px, py = parent.winfo_x(), parent.winfo_y()
            pw, ph = parent.winfo_width(), parent.winfo_height()
            cx, cy = px + (pw // 2), py + (ph // 2)

            x = cx - (w // 2)
            y = cy - (h // 2)
        except Exception:
            x = (sw - w) // 2
            y = (sh - h) // 2

        x = max(10, min(x, sw - w - 10))
        y = max(10, min(y, sh - h - 40))

        self.geometry(f"{w}x{h}+{x}+{y}")
        self.resizable(False, False)

        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill="both", expand=True)

        lbl_info = ttk.Label(
            main_frame,
            text="원하는 X축(가로) 및 Y축(세로) 픽셀 크기를 입력하세요:\n(세로 높이만 지정하려면 가로 칸을 비워두세요)",
            font=("맑은 고딕", 9)
        )
        lbl_info.pack(anchor="w", pady=(0, 15))

        entry_frame = ttk.Frame(main_frame)
        entry_frame.pack(fill="x", pady=(0, 20))

        ttk.Label(entry_frame, text="가로 (X축):", font=("맑은 고딕", 9, "bold")).pack(side="left", padx=(0, 4))
        self.ent_w = ttk.Entry(entry_frame, width=8, justify="center")
        self.ent_w.insert(0, prev_w)
        self.ent_w.pack(side="left", padx=(0, 10))

        ttk.Label(entry_frame, text="X", font=("맑은 고딕", 10, "bold"), foreground="#64748b").pack(side="left", padx=(0, 10))

        ttk.Label(entry_frame, text="세로 (Y축):", font=("맑은 고딕", 9, "bold")).pack(side="left", padx=(0, 4))
        self.ent_h = ttk.Entry(entry_frame, width=8, justify="center")
        self.ent_h.insert(0, prev_h)
        self.ent_h.pack(side="left")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(anchor="e")

        btn_ok = ttk.Button(btn_frame, text="확인 (Apply)", command=self.on_ok, width=12)
        btn_ok.pack(side="left", padx=(0, 6))

        btn_cancel = ttk.Button(btn_frame, text="취소 (Cancel)", command=self.on_cancel, width=10)
        btn_cancel.pack(side="left")

        self.bind("<Return>", lambda e: self.on_ok())
        self.bind("<Escape>", lambda e: self.on_cancel())

        self.ent_w.focus_set()

    def on_ok(self):
        w_val = self.ent_w.get().strip()
        h_val = self.ent_h.get().strip()

        w_num = "".join(filter(str.isdigit, w_val))
        h_num = "".join(filter(str.isdigit, h_val))

        if w_num and h_num:
            self.result = f"{w_num}x{h_num}"
        elif h_num:
            self.result = f"-2x{h_num}"
        elif w_num:
            self.result = f"{w_num}x-2"
        else:
            self.result = None

        self.destroy()

    def on_cancel(self):
        self.result = None
        self.destroy()

# [v4.649] 둥근 알약(Pill Button) 형태의 자막 버튼 테마 - 글자 테두리 제거 (borderw=0), 단색 흰색 기본
CAPTION_THEMES = {
    "🤍 미니멀 글래스 (기본값)": {
        'fontcolor': '#ffffff',
        'bordercolor': 'none',
        'borderw': '0',
        'boxcolor': '#0f172a@0.65',
        'boxborderw': '10',
        'canvas_bg': '#1e293b',
        'desc': '단아하고 투명감이 돋보이는 모던 다크 글래스 알약 버튼 (기본값)'
    },
    "🌈 레인보우 네온 (버튼형)": {
        'fontcolor': '#ffffff',
        'bordercolor': 'none',
        'borderw': '0',
        'boxcolor': '#1e1b4b@0.85',
        'boxborderw': '10',
        'canvas_bg': '#312e81',
        'desc': '네온 블루 테두리와 딥 바이올렛 배경의 입체적인 레인보우 버튼'
    },
    "🍬 비비드 핑크 캡슐": {
        'fontcolor': '#ffffff',
        'bordercolor': 'none',
        'borderw': '0',
        'boxcolor': '#881337@0.85',
        'boxborderw': '10',
        'canvas_bg': '#9f1239',
        'desc': '상큼하고 또렷한 마젠타 핑크 캡슐 버튼'
    },
    "💚 에메랄드 민트 버튼": {
        'fontcolor': 'white',
        'bordercolor': '#10b981',
        'borderw': '2',
        'boxcolor': '#064e3b@0.85',
        'boxborderw': '10',
        'canvas_bg': '#047857',
        'desc': '산뜻한 민트 그린 캡슐 버튼'
    },
    "🖤 럭셔리 골드 앤 네이비": {
        'fontcolor': '#fef08a',
        'bordercolor': '#eab308',
        'borderw': '2',
        'boxcolor': '#172554@0.9',
        'boxborderw': '10',
        'canvas_bg': '#1e3a8a',
        'desc': '선명한 골드 폰트와 딥 네이비 캡슐 버튼'
    },
    "🧡 선셋 오렌지 버튼": {
        'fontcolor': 'white',
        'bordercolor': '#f97316',
        'borderw': '2',
        'boxcolor': '#7c2d12@0.85',
        'boxborderw': '10',
        'canvas_bg': '#c2410c',
        'desc': '따뜻하고 부드러운 오렌지 캡슐 버튼'
    }
}


class AppConfigManager:
    """[v4.61] 프로그램 설정, 초기 시작 경로 및 인코딩 방식 프로필 보관 관리자"""
    def __init__(self, config_file="app_config.json"):
        self.config_file = config_file
        self.data = self.load_config()

    def load_config(self):
        default_config = {
            "initial_startup_dir": "",
            "encoding_profile": {
                "hw": "CPU 전용 (호환성 최상)",
                "codec": "AV1 (차세대 초고압축, 추천)",
                "format": "MKV (.mkv)",
                "res": "원본 유지",
                "fps": "원본 유지",
                "audio": "원본 유지 (기본값)",
                "crf": 28,
                "merge_mode": False,
                "merge_fit": "늘리기 (Stretch - 비율 무시 화면 꽉 채우기)"
            }
        }
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        default_config.update(loaded)
            except Exception:
                pass
        return default_config

    def save_config(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


class SmartVideoCompressorApp:
    def __init__(self, root):
        self.root = root
        global active_app
        active_app = self

        self.build_version = "v4.67g (Build 20260728 - Original File Protection & Auto Numbering Engine)"
        self.root.title(f"스마트 동영상 압축기 {self.build_version} - 배치 & GPU 최적화 & 회전/자막")

        # [v4.62] 프로그램 설정, 초기 시작 경로 및 인코딩 프로필 보관 관리자
        # [v4.65s FIX] app_config.json이 CWD(현재 작업 디렉토리) 기준으로 생성되어
        # 동영상 출력 폴더 등 엉뚱한 위치에 생성되는 문제 수정.
        # sys.executable(EXE) 또는 __file__(스크립트) 기준으로 앱 폴더를 고정 산출함.
        import sys as _sys
        _app_dir = Path(getattr(_sys, 'frozen', False) and _sys.executable or __file__).resolve().parent
        _config_path = str(_app_dir / "app_config.json")
        self.nas_manager = AppConfigManager(_config_path)

        # 애플리케이션 상태 변수 초기화 (center_window 호출 전에 먼저 설정)
        self.file_list = []
        self.is_running = False
        self.is_previewing = False
        self.current_process = None
        self.preview_process = None
        self.total_saved_bytes = 0
        self.start_time = 0
        self.encoders_cache = None       # ffmpeg -encoders 결과 캐시
        self.encoder_test_cache = {}     # 인코더 '실제 동작' 테스트 결과 캐시
        self.hw_fallback_notified = set()  # HW→CPU 자동 전환 안내 여부
        self.preview_temp_dir = None     # 미리보기 임시 폴더
        self._auto_clean_old_versions()  # [v4.67e] 구버전 파일(old/ 및 old/dist/ 이관) 자동 정리
        # [v3.9] 미리보기 길이(초): 버튼·클릭 비교 및 자동화질 표본 추출 시 공용 반영
        self.preview_duration_var = tk.StringVar(value="1")
        self.crf_combo_editor = None     # 목록 내 개별 화질 콤보박스(셀 편집기)
        self.crf_tooltip = None          # [v3.4] 개별 화질 상세 툴팁 창
        self.crf_tooltip_row = None      # [v3.4] 툴팁이 표시 중인 행 id
        self._compare_encoding_item = None  # [v3.5] 미리보기 인코딩 중 항목(목록 상태 표시)
        self.info_tooltip = None         # [v3.9] 목록 전체 정보 툴팁 창
        self.info_tooltip_key = None     # [v3.9] 툴팁이 표시 중인 (행, 종류)
        self.bulk_crf_menu = None        # [v3.9] 개별 화질 헤더 일괄 적용 메뉴

        # [v3.9] 미리보기(전/후 비교) 팝업 상태: 더블클릭·버튼 공용
        self.preview_popup_state = None

        # [v3.3] 자동화질 정밀 분석 상태
        self.auto_quality_profile_value = "동일화질(보수적)"
        self.precise_quality_running = False
        self.precise_quality_cancel = False
        self.precise_quality_process = None
        self.libvmaf_available_cache = None
        self.precise_quality_generation = 0

        # [v3.0] 저장 위치 / 파일명 설정
        self.output_mode = tk.StringVar(value='source')  # 'source'=원본 폴더, 'custom'=지정 폴더
        self.output_dir = ""                             # 지정 저장 폴더 (custom 모드)
        # [v4.65g] 파일명 저장 모드: 'encode_info'(기본), 'keep_name'(파일명만), 'keep_meta'(파일명+정보유지)
        self.filename_mode_var = tk.StringVar(value="새로운 파일명 사용(기존명칭+인코딩 정보)")
        self.keep_orig_name = tk.BooleanVar(value=False) # 하위 호환성 유지용 (내부 파생 변수)
        self.delete_orig_file = tk.BooleanVar(value=False) # [v4.2] 작업 완료 후 원본 파일 삭제 여부
        self.skip_info_file = tk.BooleanVar(value=False) # [v4.5] info 파일 생성 생략
        self.skip_duplicate_files = tk.BooleanVar(value=False) # [v4.631] 기본값: 체크 해제
        self.merge_mode = tk.BooleanVar(value=False)     # [v4.60] 체크 표시 항목 1개 파일로 병합 모드
        self.merge_caption_mode = tk.BooleanVar(value=False) # [v4.631] 기본값: 체크 해제
        self.caption_duration_var = tk.StringVar(value="계속") # [v4.643] 자막 표시 시간 기본값: 계속
        self.caption_custom_sec = tk.StringVar(value="5")  # [v4.631] 사용자 지정 자막 표시 초
        self.caption_theme_var = tk.StringVar(value="🤍 미니멀 글래스 (기본값)") # [v4.645] 자막 테마 기본값: 미니멀 글래스
        self.photo_option_var = tk.StringVar(value="모션 JPEG만 작업(음성 포함)") # [v4.63] 기본값: 모션 JPEG 전용, 정지사진 제외
        self._batch_used_outputs = set()                 # 배치 내 출력 경로 충돌 방지 세트
        # [v4.60] 디버깅 리포트용 최근 명령어 및 반환 결과 추적 변수
        self.last_ffmpeg_cmd = "없음 (아직 인코딩 명령이 실행되지 않았습니다)"
        self.last_ffmpeg_returncode = "N/A"
        self.last_ffmpeg_stderr = "없음"
        self.last_preview_cmd = "없음 (아직 미리보기 명령이 실행되지 않았습니다)"
        self.last_preview_returncode = "N/A"
        self.last_preview_stderr = "없음"

        # FFmpeg 및 FFprobe 실행 파일 경로 찾기
        self.ffmpeg_path = self.get_executable_path("ffmpeg")
        self.ffprobe_path = self.get_executable_path("ffprobe")

        # 시스템 GPU 자동 감지
        self.detected_gpu_name, self.detected_gpu_vendor = self.detect_gpu_info()

        # UI 구성요소 세팅
        self.setup_styles()
        self.create_menubar()
        self.create_widgets()
        # [v4.63] 매번 기본값으로 시작 (이전 세션 설정 승계 안 함)
        # self.apply_saved_config_profile()

        # [v4.55 UX] UI 생성 완료 후 메인 작업창을 모니터 화면의 정중앙에 정확히 배치
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()

        # 화면 해상도가 메인 창 권장 크기(1200x780)보다 작거나 디스플레이 배율이 높은 경우 자동 전체화면(Maximized) 실행
        if sw < 1200 or sh < 780:
            try:
                self.root.state('zoomed')
            except Exception:
                win_w = min(sw - 20, 1120)
                win_h = min(sh - 40, 720)
                x = max(0, (sw - win_w) // 2)
                y = max(0, (sh - win_h) // 2)
                self.root.geometry(f"{win_w}x{win_h}+{x}+{y}")
        else:
            win_w = min(1280, max(1120, sw - 60))
            win_h = min(820, max(740, sh - 80))
            x = max(0, (sw - win_w) // 2)
            y = max(0, (sh - win_h) // 2)
            self.root.geometry(f"{win_w}x{win_h}+{x}+{y}")

        # 소형 노트북 해상도(1280x720)나 높은 스케일링 환경에서도 버튼 잘림 없이 수용 가능한 최소 크기
        self.root.minsize(960, 540)

        # FFmpeg 유무 검사 및 자동 다운로드
        self.root.after(500, self.check_ffmpeg_installation)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def center_window(self, win=None, width=None, height=None, parent=None):
        """[v4.55] 창 및 팝업 대화상자를 현재 메인 창의 중앙을 기준으로 정렬 배치하는 유틸리티
        - win이 self.root인 경우 화면 전체의 정중앙에 배치
        - win이 팝업 대화상자인 경우 현재 메인 창(self.root) 위치/크기의 정중앙에 배치
        - 팝업창이 메인 창이나 화면 크기보다 큰 경우에도 오버플로우 방지
        """
        target = win if win is not None else self.root
        target.update_idletasks()
        sw = target.winfo_screenwidth()
        sh = target.winfo_screenheight()

        req_w = width or target.winfo_width()
        req_h = height or target.winfo_height()

        if req_w <= 200:
            req_w = width or (1120 if target == self.root else 480)
        if req_h <= 200:
            req_h = height or (740 if target == self.root else 320)

        # 팝업창 크기가 화면 크기 한계를 넘지 않도록 제한
        req_w = min(req_w, sw - 40)
        req_h = min(req_h, sh - 60)

        if target != self.root:
            p_win = parent or self.root
            try:
                p_win.update_idletasks()
                px, py = p_win.winfo_x(), p_win.winfo_y()
                pw, ph = p_win.winfo_width(), p_win.winfo_height()
                cx, cy = px + (pw // 2), py + (ph // 2)

                x = cx - (req_w // 2)
                y = cy - (req_h // 2)
            except Exception:
                x = (sw - req_w) // 2
                y = (sh - req_h) // 2
        else:
            x = (sw - req_w) // 2
            y = (sh - req_h) // 2

        # 화면 경계 이탈 방지 (최소 10px 여백 유지)
        x = max(10, min(x, sw - req_w - 10))
        y = max(10, min(y, sh - req_h - 40))

        target.geometry(f"{req_w}x{req_h}+{x}+{y}")

    # ==================================================================
    #  실행 파일 / 코덱 관리
    # ==================================================================
    def get_codec_dir(self):
        """[v4.53] 실행 파일/스크립트 하위 ./codec/ 디렉토리 경로 반환 (없으면 자동 생성)"""
        if getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.abspath(__file__))
        codec_dir = os.path.join(app_dir, "codec")
        try:
            os.makedirs(codec_dir, exist_ok=True)
        except Exception:
            pass
        return codec_dir

    def get_executable_path(self, exe_name):
        """[v4.53] 실행 파일/코덱 검색 순서:
        1. ./codec/exe_name.exe
        2. ./codec/bin/exe_name.exe
        3. ./exe_name.exe (현재 실행 경로)
        4. ./bin/exe_name.exe
        5. PyInstaller 번들 임시 폴더 (_MEIPASS)
        6. System PATH
        """
        exe_file = f"{exe_name}.exe" if os.name == 'nt' else exe_name
        codec_dir = self.get_codec_dir()

        # 1. ./codec/exe_name.exe
        p1 = os.path.join(codec_dir, exe_file)
        if os.path.exists(p1):
            return p1

        # 2. ./codec/bin/exe_name.exe
        p2 = os.path.join(codec_dir, "bin", exe_file)
        if os.path.exists(p2):
            return p2

        if getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
            # [v4.65d] dist 폴더에서 실행 시 상위 폴더 ./codec/ffmpeg.exe 우선 감지
            parent_codec = os.path.join(os.path.dirname(app_dir), "codec", exe_file)
            if os.path.exists(parent_codec):
                return parent_codec
        else:
            app_dir = os.path.dirname(os.path.abspath(__file__))

        # 3. ./exe_name.exe
        p3 = os.path.join(app_dir, exe_file)
        if os.path.exists(p3):
            return p3

        # 4. ./bin/exe_name.exe
        p4 = os.path.join(app_dir, "bin", exe_file)
        if os.path.exists(p4):
            return p4

        # 5. PyInstaller 번들 임시 폴더 (_MEIPASS)
        meipass = getattr(sys, '_MEIPASS', '')
        if meipass:
            pm1 = os.path.join(meipass, exe_file)
            if os.path.exists(pm1):
                return pm1
            pm2 = os.path.join(meipass, "codec", exe_file)
            if os.path.exists(pm2):
                return pm2

        # 6. System PATH
        sys_path = shutil.which(exe_name)
        if sys_path:
            return sys_path
        return None

    def check_ffmpeg_installation(self):
        if not self.ffmpeg_path or not self.ffprobe_path:
            msg = ("FFmpeg(필수 코덱)이 ./codec/ 폴더나 시스템에 없습니다.\n"
                   "자동으로 다운로드 및 설치하시겠습니까? (전체 코덱 팩, 약 80~100MB)\n\n"
                   "※ 아니오를 누르면 수동 다운로드 및 배치 안내창이 열립니다.")
            if messagebox.askyesno("코덱 설치 안내", msg, parent=self.root):
                self.download_ffmpeg(full=True)
            else:
                self.show_manual_codec_guide_dialog("코덱 미설치 상태")
        else:
            self.refresh_ffmpeg_status()

    def refresh_ffmpeg_status(self):
        """헤더의 FFmpeg 설치 상태 배지 갱신"""
        self.encoder_test_cache = {}   # FFmpeg가 바뀌었을 수 있으므로 테스트 캐시 초기화
        if not hasattr(self, 'lbl_ffmpeg_status'):
            return
        if self.ffmpeg_path and self.ffprobe_path:
            self.lbl_ffmpeg_status.config(text="● 코덱(FFmpeg) 설치됨", foreground="#15803d")
        else:
            self.lbl_ffmpeg_status.config(text="● 코덱(FFmpeg) 미설치", foreground="#b91c1c")

    def get_available_encoders(self, force=False):
        """설치된 FFmpeg의 사용 가능 인코더 목록 조회 (캐시)"""
        if self.encoders_cache is not None and not force:
            return self.encoders_cache
        if not self.ffmpeg_path:
            return ""
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            res = subprocess.run([self.ffmpeg_path, '-hide_banner', '-encoders'],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, encoding='utf-8', errors='replace',
                                 creationflags=creationflags)
            self.encoders_cache = res.stdout
        except Exception:
            self.encoders_cache = ""
        return self.encoders_cache

    def is_encoder_available(self, encoder_name):
        return encoder_name in self.get_available_encoders()

    def test_encoder_works(self, encoder_name):
        """인코더가 현재 PC의 '실제 하드웨어'에서 동작하는지 초단기 테스트 인코딩으로 검증.
        FFmpeg 빌드에 인코더가 포함되어 있어도 GPU 세대가 지원하지 않으면
        런타임에 -22(Invalid argument) 오류가 발생하므로 사전에 검사 후 캐시한다."""
        if encoder_name in self.encoder_test_cache:
            return self.encoder_test_cache[encoder_name]
        if not self.is_encoder_available(encoder_name):
            self.encoder_test_cache[encoder_name] = False
            return False
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            cmd = [self.ffmpeg_path, '-hide_banner', '-v', 'error', '-y',
                   '-f', 'lavfi', '-i', 'color=c=black:s=320x240:d=0.3:r=30',
                   '-frames:v', '5', '-c:v', encoder_name, '-f', 'null',
                   'NUL' if os.name == 'nt' else '/dev/null']
            r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=20, creationflags=creationflags)
            ok = (r.returncode == 0)
        except Exception:
            ok = False
        self.encoder_test_cache[encoder_name] = ok
        return ok

    def resolve_encoder(self, hw_encoder, hw_args, cpu_encoder, cpu_args):
        """HW 인코더가 실제 동작하면 그대로 사용, 아니면 CPU 인코더로 자동 대체(최초 1회 안내)"""
        if hw_encoder and self.test_encoder_works(hw_encoder):
            return hw_encoder, hw_args
        if hw_encoder and hw_encoder not in self.hw_fallback_notified:
            self.hw_fallback_notified.add(hw_encoder)
            self.root.after(0, lambda: messagebox.showwarning(
                "하드웨어 인코더 미지원 → CPU 자동 전환",
                f"'{hw_encoder}' 하드웨어 인코더가 현재 그래픽 카드에서 동작하지 않아\n"
                f"CPU 인코더({cpu_encoder})로 자동 전환하여 작업을 계속합니다.\n\n"
                f"※ AV1 하드웨어 인코딩은 최신 세대 GPU에서만 지원됩니다.\n"
                f"   (AMD RX 7000 이상 / NVIDIA RTX 40 이상 / Intel Arc)\n"
                f"※ CPU 인코딩은 화질은 동일하나 속도가 느립니다.", parent=self.root))
        return cpu_encoder, cpu_args

    def ensure_codec_or_offer_install(self, encoder_name, friendly_name):
        """선택한 인코더가 없으면 전체 코덱 팩 설치를 제안"""
        if self.is_encoder_available(encoder_name):
            return True
        msg = (f"현재 설치된 FFmpeg에 '{friendly_name}' 인코더({encoder_name})가 없습니다.\n\n"
               f"확장 코덱이 포함된 전체 코덱 팩(Full Build)을\n"
               f"지금 다운로드하여 설치하시겠습니까? (약 80~100MB)")
        if messagebox.askyesno("확장 코덱 설치 필요", msg, parent=self.root):
            self.download_ffmpeg(full=True)
        return False

    def open_codec_folder(self):
        """[v4.53] ./codec/ 코덱 저장 폴더를 윈도우 탐색기로 열기"""
        codec_dir = self.get_codec_dir()
        try:
            if os.name == 'nt':
                os.startfile(codec_dir)
            else:
                subprocess.Popen(['xdg-open', codec_dir])
        except Exception as e:
            messagebox.showerror("폴더 열기 실패", f"코덱 폴더를 열 수 없습니다.\n{codec_dir}\n\n오류: {e}", parent=self.root)

    def show_manual_codec_guide_dialog(self, err_msg=""):
        """[v4.53] 코덱 자동 다운로드 404/실패 시 및 수동 설치 방법 안내 팝업"""
        dlg = tk.Toplevel(self.root)
        dlg.title("📁 FFmpeg 코덱 수동 수급 및 설치 안내")
        self.center_window(dlg, 570, 450)
        dlg.transient(self.root)
        dlg.grab_set()

        content_frame = ttk.Frame(dlg, padding=16)
        content_frame.pack(fill="both", expand=True)

        header_lbl = ttk.Label(content_frame, text="FFmpeg 코덱 수동 수급 & 배치 방법",
                               font=("맑은 고딕", 12, "bold"), foreground="#1e3a8a")
        header_lbl.pack(anchor="w", pady=(0, 10))

        if err_msg:
            err_box = tk.Label(content_frame, text=f"※ 안내 / 다운로드 상태:\n{err_msg}",
                               fg="#b91c1c", bg="#fef2f2", justify="left", padx=10, pady=8,
                               font=("맑은 고딕", 9), wraplength=520)
            err_box.pack(fill="x", pady=(0, 10))

        text_guide = (
            "【수동 다운로드 및 설치 순서】\n\n"
            "1. 포털 사이트(구글/네이버)에서 아래 검색어를 검색하거나 주소를 방문합니다:\n"
            "   - 공식 다운로드 페이지: https://www.gyan.dev/ffmpeg/builds/\n"
            "   - GitHub 릴리즈: https://github.com/GyanD/codexffmpeg/releases\n"
            "   - 검색어: [ gyan.dev ffmpeg ] 또는 [ codexffmpeg github ]\n\n"
            "2. 'ffmpeg-release-full.zip' (또는 full_build.zip) 파일 1개를 다운로드합니다.\n\n"
            "3. 압축 파일 안의 'bin' 폴더에서 3개 파일(ffmpeg.exe, ffprobe.exe, ffplay.exe)을 복사합니다.\n\n"
            "4. 이 프로그램이 실행되는 위치의 'codec' 하위 폴더(./codec/)에 복사한 파일들을 붙여넣으세요."
        )
        txt = tk.Text(content_frame, height=11, font=("맑은 고딕", 9), bg="#f8fafc", fg="#1e293b",
                      wrap="word", bd=1, relief="solid", padx=10, pady=10)
        txt.insert("1.0", text_guide)
        txt.config(state="disabled")
        txt.pack(fill="both", expand=True, pady=(0, 12))

        btn_box = ttk.Frame(content_frame)
        btn_box.pack(fill="x")

        def open_url():
            webbrowser.open("https://www.gyan.dev/ffmpeg/builds/")

        def copy_url():
            self.root.clipboard_clear()
            self.root.clipboard_append("https://www.gyan.dev/ffmpeg/builds/")
            messagebox.showinfo("복사 완료", "Gyan.dev 다운로드 주소가 클립보드에 복사되었습니다.", parent=dlg)

        ttk.Button(btn_box, text="🌐 공식 다운로드 페이지 열기", command=open_url).pack(side="left", padx=(0, 6))
        ttk.Button(btn_box, text="📂 코덱 폴더(./codec/) 열기", command=self.open_codec_folder).pack(side="left", padx=(0, 6))
        ttk.Button(btn_box, text="📋 주소 복사", command=copy_url).pack(side="left", padx=(0, 6))
        ttk.Button(btn_box, text="닫기", command=dlg.destroy).pack(side="right")

    def show_installed_codecs(self):
        """설치된 주요 인코더 확인 창"""
        if not self.ffmpeg_path:
            self.show_manual_codec_guide_dialog("FFmpeg가 설치되어 있지 않습니다.")
            return
        checks = [
            ("H.264 (libx264)", "libx264"), ("H.265/HEVC (libx265)", "libx265"),
            ("AV1 (libsvtav1)", "libsvtav1"), ("VP9 (libvpx-vp9)", "libvpx-vp9"),
            ("NVIDIA HEVC (hevc_nvenc)", "hevc_nvenc"), ("NVIDIA H.264 (h264_nvenc)", "h264_nvenc"),
            ("AMD HEVC (hevc_amf)", "hevc_amf"), ("Intel HEVC (hevc_qsv)", "hevc_qsv"),
        ]
        self.get_available_encoders(force=True)
        lines = [f"FFmpeg 경로: {self.ffmpeg_path}", ""]
        for name, enc in checks:
            mark = "✅ 사용 가능" if self.is_encoder_available(enc) else "❌ 미설치"
            lines.append(f"{mark}  |  {name}")
        lines.append("")
        lines.append(f"※ 코덱 저장 경로: {self.get_codec_dir()}")
        lines.append("※ 미설치 코덱이 필요하면 [도구 > 전체 코덱 팩 설치]를 이용하세요.")
        messagebox.showinfo("설치된 코덱 확인", "\n".join(lines), parent=self.root)

    def download_ffmpeg(self, full=False):
        """[v4.53] GitHub API 동적 다운로드 URL 파싱 및 ./codec/ 하위 폴더 추출 설치"""
        if hasattr(self, 'btn_start'):
            self.btn_start.config(state="disabled")

        pack_name = "전체 코덱 팩 (Full Build)"

        dl_window = tk.Toplevel(self.root)
        dl_window.title(f"{pack_name} 다운로드 중...")
        self.center_window(dl_window, 440, 170)
        dl_window.transient(self.root)
        dl_window.grab_set()

        ttk.Label(dl_window,
                  text=f"{pack_name}을 다운로드하고 있습니다.\n서버에서 코덱 URL을 동적으로 확인 중입니다...",
                  justify="center").pack(pady=15)
        progress = ttk.Progressbar(dl_window, mode='determinate', length=340)
        progress.pack(pady=10)
        status_lbl = ttk.Label(dl_window, text="연결 중...")
        status_lbl.pack()

        def dl_thread():
            try:
                # 1. GitHub API 최신 릴리즈 동적 조회 (404 예방)
                download_url = None
                target_keyword = "full_build.zip"
                fallback_url = "https://github.com/GyanD/codexffmpeg/releases/download/8.1.2/ffmpeg-8.1.2-full_build.zip"

                try:
                    api_req = urllib.request.Request(
                        "https://api.github.com/repos/GyanD/codexffmpeg/releases/latest",
                        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                    )
                    with urllib.request.urlopen(api_req, timeout=8) as api_res:
                        if api_res.status == 200:
                            data = json.loads(api_res.read().decode('utf-8'))
                            for asset in data.get('assets', []):
                                aname = asset.get('name', '').lower()
                                # [v4.65l] 항상 full_build만 사용 (essentials 제거)
                                if 'full' in aname and aname.endswith('.zip'):
                                    download_url = asset.get('browser_download_url')
                                    break
                except Exception:
                    pass

                if not download_url:
                    download_url = fallback_url

                req = urllib.request.Request(download_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

                with urllib.request.urlopen(req, timeout=60) as response:
                    total_length = response.headers.get('content-length')
                    total_length = int(total_length) if total_length else 0

                    downloaded = 0
                    chunk_size = 32768
                    data = b""

                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        data += chunk
                        downloaded += len(chunk)
                        if total_length:
                            pct = int((downloaded / total_length) * 100)
                            self.root.after(0, lambda p=pct: progress.config(value=p))
                            self.root.after(0, lambda p=pct: status_lbl.config(text=f"{p}% 완료 ({downloaded // (1024*1024)}MB / {total_length // (1024*1024)}MB)"))
                        else:
                            self.root.after(0, lambda d=downloaded: status_lbl.config(text=f"다운로드 중... ({d // (1024*1024)}MB)"))

                    self.root.after(0, lambda: status_lbl.config(text="압축 해제 및 ./codec/ 저장 중..."))

                    # ./codec/ 서브 디렉토리에 ffmpeg.exe, ffprobe.exe, ffplay.exe 평탄화 해제
                    target_dir = self.get_codec_dir()
                    with zipfile.ZipFile(io.BytesIO(data)) as z:
                        for file_info in z.infolist():
                            fname = file_info.filename.lower()
                            if fname.endswith('ffmpeg.exe') or fname.endswith('ffprobe.exe') or fname.endswith('ffplay.exe'):
                                file_info.filename = os.path.basename(file_info.filename)
                                z.extract(file_info, target_dir)

                    self.root.after(0, self.on_ffmpeg_downloaded, dl_window, True, "")
            except Exception as e:
                self.root.after(0, self.on_ffmpeg_downloaded, dl_window, False, str(e))

        threading.Thread(target=dl_thread, daemon=True).start()

    def on_ffmpeg_downloaded(self, dl_window, success, err_msg):
        dl_window.destroy()
        if success:
            self.ffmpeg_path = self.get_executable_path("ffmpeg")
            self.ffprobe_path = self.get_executable_path("ffprobe")
            self.encoders_cache = None  # 코덱 목록 캐시 초기화
            if self.ffmpeg_path and self.ffprobe_path:
                if hasattr(self, 'btn_start'):
                    self.btn_start.config(state="normal")
                self.refresh_ffmpeg_status()
                messagebox.showinfo("설치 완료",
                                    f"코덱 다운로드 및 설치가 성공적으로 완료되었습니다!\n\n"
                                    f"코덱 저장 위치: {self.get_codec_dir()}\n"
                                    f"이제 인코딩 작업을 진행하실 수 있습니다.", parent=self.root)
            else:
                self.show_manual_codec_guide_dialog("다운로드는 완료되었으나 ./codec/ 폴더에서 실행 파일(ffmpeg.exe)을 찾을 수 없습니다.")
        else:
            self.show_manual_codec_guide_dialog(err_msg)

    # ==================================================================
    #  GPU 감지
    # ==================================================================
    def detect_gpu_info(self):
        gpu_name = "알 수 없는 장치 (또는 인식 불가)"
        vendor = "CPU"

        if os.name == 'nt':
            try:
                import winreg
                key_path = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                    num_subkeys = winreg.QueryInfoKey(key)[0]
                    gpus = []

                    for i in range(num_subkeys):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            if subkey_name.isdigit():
                                with winreg.OpenKey(key, subkey_name) as subkey:
                                    desc, _ = winreg.QueryValueEx(subkey, "DriverDesc")
                                    if desc and "Virtual" not in desc and "RDP" not in desc:
                                        gpus.append(desc)
                        except OSError:
                            continue

                    if gpus:
                        for name in gpus:
                            upper_name = name.upper()
                            if "NVIDIA" in upper_name or "AMD" in upper_name or "RADEON" in upper_name or "RX " in upper_name:
                                gpu_name = name
                                break
                        else:
                            if gpus:
                                gpu_name = gpus[0]
            except Exception as e:
                print(f"GPU Registry 감지 실패: {e}")

        name_upper = gpu_name.upper()
        if "NVIDIA" in name_upper:
            vendor = "NVIDIA"
        elif "AMD" in name_upper or "RADEON" in name_upper or "RX " in name_upper:
            vendor = "AMD"
        elif "INTEL" in name_upper or "HD GRAPHICS" in name_upper or "UHD GRAPHICS" in name_upper:
            vendor = "Intel"

        return gpu_name, vendor

    # ==================================================================
    #  스타일 / 메뉴 / UI
    # ==================================================================
    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')

        self.BG_COLOR = "#f4f6f8"
        self.CARD_BG = "#ffffff"
        self.ACCENT = "#2563eb"
        self.ACCENT_DARK = "#1d4ed8"
        self.TEXT_MAIN = "#1f2937"
        self.TEXT_SUB = "#6b7280"

        self.root.configure(bg=self.BG_COLOR)

        base_font = ("맑은 고딕", 10)
        self.style.configure('TFrame', background=self.BG_COLOR)
        self.style.configure('Card.TFrame', background=self.CARD_BG)
        self.style.configure('TLabel', background=self.BG_COLOR, foreground=self.TEXT_MAIN, font=base_font)
        self.style.configure('Sub.TLabel', foreground=self.TEXT_SUB, font=("맑은 고딕", 9))
        self.style.configure('Header.TLabel', font=("맑은 고딕", 13, "bold"), foreground=self.TEXT_MAIN)
        self.style.configure('Accent.TLabel', foreground=self.ACCENT, font=("맑은 고딕", 10, "bold"))
        self.style.configure('TLabelframe', background=self.BG_COLOR, font=("맑은 고딕", 10, "bold"))
        self.style.configure('TLabelframe.Label', background=self.BG_COLOR, foreground=self.ACCENT,
                             font=("맑은 고딕", 10, "bold"))

        # ── 버튼 그룹별 차분한 낮은 채도 파스텔/슬레이트 스타일 [v4.60 UX] ─────────────
        # 1. 상단 툴바: 파일/폴더 추가 버튼 (차분한 슬레이트 블루)
        self.style.configure('Add.TButton', font=("맑은 고딕", 9),
                             background="#475569", foreground="white", padding=5)
        self.style.map('Add.TButton',
                       background=[('active', '#334155'), ('disabled', '#cbd5e1')])

        # 2. 상단 툴바: 삭제 / 비우기 버튼 (차분한 슬레이트 버건디/로즈)
        self.style.configure('Danger.TButton', font=("맑은 고딕", 9),
                             background="#70424a", foreground="white", padding=5)
        self.style.map('Danger.TButton',
                       background=[('active', '#542831'), ('disabled', '#e2e8f0')])

        # 3. 상단 툴바: 완료 항목 재작업 버튼 (차분한 슬레이트 인디고)
        self.style.configure('Reset.TButton', font=("맑은 고딕", 9),
                             background="#56506d", foreground="white", padding=5)
        self.style.map('Reset.TButton',
                       background=[('active', '#3f3954'), ('disabled', '#e2e8f0')])

        # ── 하단 핵심 컨트롤 버튼 (높은 선명도/고대비로 가장 눈에 잘 띔) ──
        # 4. 하단 핵심 버튼: ▶ 작업 시작 (선명한 파란색 / 에메랄드)
        self.style.configure('Primary.TButton', font=("맑은 고딕", 10, "bold"),
                             background="#2563eb", foreground="white", padding=(12, 6))
        self.style.map('Primary.TButton',
                       background=[('active', '#1d4ed8'), ('disabled', '#cbd5e1')])

        # 5. 하단 핵심 버튼: ■ 작업 취소 (선명한 레드)
        self.style.configure('Cancel.TButton', font=("맑은 고딕", 10, "bold"),
                             background="#dc2626", foreground="white", padding=(12, 6))
        self.style.map('Cancel.TButton',
                       background=[('active', '#b91c1c'), ('disabled', '#fca5a5')])

        self.style.configure('Preview.TButton', font=("맑은 고딕", 10, "bold"),
                             background="#0d9488", foreground="white", padding=6)
        self.style.map('Preview.TButton',
                       background=[('active', '#0f766e'), ('disabled', '#99f6e4')])

        # ── 콤보박스 직관적 색상 커스텀: 활성화(선택가능) -> 흰색 배경 / 비활성화 -> 회색 배경 [v4.55 UX] ──
        self.style.configure('TCombobox', padding=3, font=("맑은 고딕", 9))
        self.style.map('TCombobox',
                       fieldbackground=[('disabled', '#e5e7eb'), ('readonly', '#ffffff'), ('!disabled', '#ffffff')],
                       background=[('disabled', '#e5e7eb'), ('readonly', '#ffffff'), ('!disabled', '#ffffff')],
                       foreground=[('disabled', '#9ca3af'), ('readonly', '#1f2937'), ('!disabled', '#1f2937')])

        self.style.configure("Treeview", font=("맑은 고딕", 9), rowheight=24)
        self.style.configure("Treeview.Heading", font=("맑은 고딕", 9, "bold"))

    def create_menubar(self):
        menubar = tk.Menu(self.root)

        # 파일 메뉴
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="파일 추가...", command=self.add_files, accelerator="Ctrl+O")
        file_menu.add_command(label="폴더 추가 (하위 폴더 포함)...", command=self.add_folder,
                              accelerator="Ctrl+Shift+O")
        file_menu.add_command(label="선택 항목 삭제", command=self.remove_selected, accelerator="Del")
        file_menu.add_command(label="🔍 대기열 중복 파일 탐색 및 자동 제외", command=lambda: self.filter_duplicates_in_queue(show_msg=True))
        file_menu.add_command(label="목록 전체 비우기", command=self.clear_all)
        file_menu.add_separator()
        file_menu.add_command(label="종료", command=self.on_close)
        menubar.add_cascade(label="파일", menu=file_menu)

        # 도구 메뉴 (코덱 설치 포함)
        tools_menu = tk.Menu(menubar, tearoff=0)
        # [v4.65l] 에센스 제거 - 풀버전만 사용
        tools_menu.add_command(label="코덱 자동 설치 (Full Build - MKV/AV1/VP9 확장 지원, 약 100MB)",
                               command=lambda: self.download_ffmpeg(full=True))
        tools_menu.add_separator()
        tools_menu.add_command(label="수동 코덱 다운로드 링크 및 배치 안내...", command=self.show_manual_codec_guide_dialog)
        tools_menu.add_command(label="코덱 저장 폴더(./codec/) 열기", command=self.open_codec_folder)
        tools_menu.add_separator()
        tools_menu.add_command(label="설치된 코덱 확인", command=self.show_installed_codecs)
        tools_menu.add_separator()
        tools_menu.add_command(label="🐞 디버깅용 현재 상태 클립보드에 복사", command=self.copy_debug_info_to_clipboard)
        tools_menu.add_separator()
        tools_menu.add_command(label="🔍 대기열 중복 영상/사진 탐색 및 제외 정돈", command=lambda: self.filter_duplicates_in_queue(show_msg=True))
        tools_menu.add_command(label="미리보기 (무작위 인코딩 미리보기)", command=self.start_preview)
        menubar.add_cascade(label="도구", menu=tools_menu)

        # 도움말 메뉴
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="프로그램 정보", command=self.show_about)
        menubar.add_cascade(label="도움말", menu=help_menu)

        self.root.config(menu=menubar)
        self.root.bind("<Control-o>", lambda e: self.add_files())
        self.root.bind("<Control-O>", lambda e: self.add_folder())

    def copy_debug_info_to_clipboard(self):
        """[v4.60] 디버깅을 위해 현재 UI 설정, 작업 내부 플래그, 파일 대기열 상태를 클립보드로 복사"""
        try:
            lines = [
                "==================================================",
                f"📋 스마트 동영상 압축기 디버깅 리포트 ({self.build_version})",
                f"⏰ 생성 시각: {time.strftime('%Y-%m-%d %H:%M:%S')}",
                "==================================================",
                "",
                "[1. 현재 GUI 설정 상태]",
                f"• 가속 장치 (combo_hw): {self.combo_hw.get() if hasattr(self, 'combo_hw') else 'N/A'}",
                f"• 출력 코덱 (combo_codec): {self.combo_codec.get() if hasattr(self, 'combo_codec') else 'N/A'}",
                f"• 출력 포맷 (combo_format): {self.combo_format.get() if hasattr(self, 'combo_format') else 'N/A'}",
                f"• 해상도 변경 (combo_res): {self.combo_res.get() if hasattr(self, 'combo_res') else 'N/A'}",
                f"• 프레임(FPS) (combo_fps): {self.combo_fps.get() if hasattr(self, 'combo_fps') else 'N/A'}",
                f"• 오디오 품질 (combo_audio): {self.combo_audio.get() if hasattr(self, 'combo_audio') else 'N/A'}",
                f"• 화질(CRF 값): {self.crf_var.get() if hasattr(self, 'crf_var') else 'N/A'}",
                f"• 화질 기준 (auto_quality): {self.auto_quality_profile_var.get() if hasattr(self, 'auto_quality_profile_var') else 'N/A'}",
                f"• 저장 위치 모드 (output_mode): {self.output_mode.get() if hasattr(self, 'output_mode') else 'N/A'}",
                f"• 지정 저장 폴더 (output_dir): {self.output_dir if hasattr(self, 'output_dir') else 'N/A'}",
                f"• 파일명 저장 모드 (filename_mode): {self.filename_mode_var.get() if hasattr(self, 'filename_mode_var') else 'N/A'}",
                f"• 1개 파일 병합 모드 (merge_mode): {self.merge_mode.get() if hasattr(self, 'merge_mode') else 'N/A'}",
                f"• 병합 화면 맞춤 모드 (merge_fit): {self.combo_merge_fit.get() if hasattr(self, 'combo_merge_fit') else 'N/A'}",
                f"• 미리보기 설정 길이 (preview_duration_var): {self.preview_duration_var.get() if hasattr(self, 'preview_duration_var') else 'N/A'}",
                "",
                "[2. 애플리케이션 내부 실행 플래그]",
                f"• is_running (배치 실행 중): {self.is_running}",
                f"• is_previewing (미리보기 실행 중): {self.is_previewing}",
                f"• precise_quality_running (정밀계산 중): {self.precise_quality_running}",
                f"• ffmpeg_path: {self.ffmpeg_path}",
                f"• ffprobe_path: {self.ffprobe_path}",
                f"• current_process: {self.current_process}",
                f"• preview_process: {self.preview_process}",
                "",
                "[3. 대기열 파일 목록 정보]",
                f"• 총 파일 개수: {len(self.file_list)}개",
            ]

            for idx, item in enumerate(self.file_list, 1):
                lines.append(
                    f"  [{idx}] {item.get('name')} | 상태: '{item.get('status')}' | checked: {item.get('checked')} | "
                    f"duration: {item.get('duration')}s | orig_codec: {item.get('orig_codec')} | orig_res: {item.get('orig_res')}"
                )

            lines.extend([
                "",
                "[4. 최근 작업 실행 명령어 및 FFmpeg 반환 결과 요약]",
                f"• 최근 배치/인코딩 명령어:",
                f"  {getattr(self, 'last_ffmpeg_cmd', '없음')}",
                f"• 최근 배치 작업 반환 코드: {getattr(self, 'last_ffmpeg_returncode', 'N/A')}",
                f"• 최근 배치 stderr 로그 (상세):",
                f"{getattr(self, 'last_ffmpeg_stderr', '없음')}",
                "",
                f"• 최근 미리보기 인코딩 명령어:",
                f"  {getattr(self, 'last_preview_cmd', '없음')}",
                f"• 최근 미리보기 반환 코드: {getattr(self, 'last_preview_returncode', 'N/A')}",
                f"• 최근 미리보기 stderr 로그 (상세):",
                f"{getattr(self, 'last_preview_stderr', '없음')}",
            ])

            # [v4.631c] 파일 분석 진단 정보 섹션
            stats = getattr(self, '_analyze_stats', {})
            if stats:
                lines.extend([
                    "",
                    "[5. 파일 분석 진단 정보 (최근 분석 세션)]",
                    f"• 분석 입력 파일 수: {stats.get('total_input', 'N/A')}개",
                    f"• 대기열 최종 추가: {stats.get('processed', 'N/A')}개",
                    f"• 정지사진 감지 (is_jpeg & !audio & dur<=0.5): {stats.get('static_photo', 0)}개",
                    f"• 모션 JPEG 감지 (is_jpeg & (audio|dur>0.5)): {stats.get('motion_jpeg', 0)}개",
                    f"• 일반 동영상 감지: {stats.get('general_video', 0)}개",
                    f"• 정지사진 필터 제외 ('모션 JPEG만' 옵션): {stats.get('skipped_photo_filter', 0)}개",
                    f"• 경로 미발견 스킵: {stats.get('path_not_found', 0)}개",
                    f"• 이미 대기열 존재 스킵: {stats.get('already_in_list', 0)}개",
                    f"• 비디오 스트림 없음 스킵: {stats.get('no_video_stream', 0)}개",
                    f"• ffprobe 실패: {stats.get('ffprobe_error', 0)}개",
                    f"• ffprobe 타임아웃(5초 초과): {stats.get('timeout_error', 0)}개",
                    f"• 정지사진 옵션 (분석 시작 시): {stats.get('photo_option_at_start', 'N/A')}",
                    f"• 정지사진 옵션 (현재): {self.photo_option_var.get() if hasattr(self, 'photo_option_var') else 'N/A'}",
                    f"• 자막 표시 모드: {self.caption_duration_var.get() if hasattr(self, 'caption_duration_var') else 'N/A'}",
                    f"• 중복 제외 체크: {self.skip_duplicate_files.get() if hasattr(self, 'skip_duplicate_files') else 'N/A'}",
                ])
                # ffprobe 샘플 결과 및 상세 판별 사유 코드 (Reason Code)
                samples = stats.get('sample_ffprobe_results', [])
                if samples:
                    lines.append("")
                    lines.append("  [ffprobe 샘플 결과 & 상태 판별 진단 (Reason Code)]")
                    for si, s in enumerate(samples[:5], 1):
                        lines.append(f"  --- 샘플 {si}: {s.get('name', 'N/A')} ---")
                        lines.append(f"      📌 상태 코드 (Reason Code): {s.get('reason_code', 'N/A')}")
                        lines.append(f"      has_audio: {s.get('has_audio')}, raw_dur: {s.get('raw_dur')}, is_jpeg_ext: {s.get('is_jpeg_ext')}")
                        lines.append(f"      is_static_photo: {s.get('is_static_photo')}, codec: {s.get('codec_name')}")
                        lines.append(f"      v_dur: {s.get('v_dur')}, a_dur: {s.get('a_dur')}, fmt_dur: {s.get('fmt_dur')}")
                        lines.append(f"      audio_codec: {s.get('audio_codec')}, width: {s.get('width')}, height: {s.get('height')}")
                # 정지사진 자동 제외 판별 상세 샘플 목록 (최대 15건)
                skipped_details = stats.get('skipped_photo_details', [])
                if skipped_details:
                    lines.append("")
                    lines.append(f"  [🖼️ 정지사진 자동 제외 판별 상세 샘플 (총 {len(skipped_details)}건)]")
                    for s_idx, p_info in enumerate(skipped_details[:15], 1):
                        audio_st = "있음" if p_info.get('has_audio') else "없음"
                        reason = p_info.get('reason', '정지사진 필터 제외')
                        lines.append(
                            f"  [{s_idx}] {p_info.get('name')} | 판별 사유: {reason} | 음성: {audio_st} | "
                            f"재생시간: {p_info.get('dur', 0):.2f}s | 해상도: {p_info.get('res')}"
                        )
                # 예외 목록
                exceptions = stats.get('exceptions', [])
                if exceptions:
                    lines.append("")
                    lines.append(f"  [분석 중 예외 발생 ({len(exceptions)}건)]")
                    for ei, ex in enumerate(exceptions[:10], 1):
                        lines.append(f"  [{ei}] {ex}")
            lines.extend([
                "",
                "==================================================",
                "[6. 최근 콘솔 실제 실행 명령어 및 전체 에러 텍스트 (명령창 출력)]",
                "==================================================",
                f"• 최근 콘솔 실행 명령어 (Full CLI Command Line):",
                f"  {getattr(self, 'last_ffmpeg_cmd', '없음 (아직 명령이 실행되지 않았습니다)')}",
                "",
                f"• 명령어 반환 코드 (Return Code): {getattr(self, 'last_ffmpeg_returncode', 'N/A')}",
                "",
                f"• 콘솔 실행 텍스트 / 에러 출력 (Full Console Stderr Output):",
                "--------------------------------------------------",
                f"{getattr(self, 'last_ffmpeg_stderr', '없음')}",
                "--------------------------------------------------"
            ])

            report_text = "\n".join(lines)
            self.root.clipboard_clear()
            self.root.clipboard_append(report_text)
            self.root.update()

            messagebox.showinfo(
                "📋 클립보드 복사 완료",
                "현재 스마트 동영상 압축기의 전체 상태 및 디버깅 정보가 클립보드에 복사되었습니다.\n\n"
                "대화창에 Ctrl+V 로 붙여넣어 주시면 정확한 원인 분석에 큰 도움이 됩니다!", parent=self.root)
        except Exception as e:
            messagebox.showerror("오류", f"디버깅 정보 복사 중 오류가 발생했습니다: {e}", parent=self.root)

    def show_about(self):
        messagebox.showinfo(
            "프로그램 정보",
            f"스마트 동영상 압축기 {self.build_version}\n\n"
            "· 개발자: 이건전 (soundly@goedu.kr)\n\n"
            "· 배치(일괄) 압축 및 GPU 하드웨어 가속 지원\n"
            "· H.264 / H.265 / AV1 / VP9 / MKV(Matroska) 방식 지원\n"
            "· 영상별 90°/180° 회전 및 좌우 반전 필터 지원\n"
            "· 동영상 병합 시 우측 하단 5초 파일명 자막 오버레이 지원\n"
            "· 압축 전/후 미리보기 비교 기능", parent=self.root)

    def create_widgets(self):
        # ── 상단 헤더 바 ─────────────────────────────────────────
        header = tk.Frame(self.root, bg=self.CARD_BG, highlightbackground="#d1d5db",
                          highlightthickness=1)
        header.pack(fill="x", padx=12, pady=(6, 0))

        tk.Label(header, text="스마트 동영상 압축기", bg=self.CARD_BG, fg=self.TEXT_MAIN,
                 font=("맑은 고딕", 13, "bold")).pack(side="left", padx=12, pady=5)
        tk.Label(header, text=self.build_version, bg=self.CARD_BG, fg=self.TEXT_SUB,
                 font=("맑은 고딕", 9)).pack(side="left", pady=5)

        self.lbl_ffmpeg_status = tk.Label(header, text="● 코덱 확인 중...", bg=self.CARD_BG,
                                          fg=self.TEXT_SUB, font=("맑은 고딕", 9, "bold"))
        self.lbl_ffmpeg_status.pack(side="right", padx=14)

        tk.Label(header, text=f"그래픽 카드: [{self.detected_gpu_vendor}] {self.detected_gpu_name}",
                 bg=self.CARD_BG, fg=self.ACCENT, font=("맑은 고딕", 9, "bold")).pack(side="right", padx=14)

        # ── 메인 영역 (고정 레이아웃: 조절 분할선 제거로 이동 불가) ──────────────
        main_container = ttk.Frame(self.root)
        main_container.pack(fill="both", expand=True, padx=12, pady=6)

        # [1] 작업 대기열 (드래그 조절선 없이 상단 가변 영역 사용)
        frame_queue = ttk.LabelFrame(main_container, text=" 📁 작업 대기열 (진행 현황) ", padding=6)
        frame_queue.pack(fill="both", expand=True, pady=(0, 6))

        btn_frame = ttk.Frame(frame_queue)
        btn_frame.pack(fill="x", pady=(0, 4))
        self.btn_add_files = ttk.Button(btn_frame, text="➕ 파일 추가", style='Add.TButton', command=self.add_files)
        self.btn_add_files.pack(side="left")
        self.btn_add_folder = ttk.Button(btn_frame, text="📂 폴더 추가 (하위 포함)", style='Add.TButton', command=self.add_folder)
        self.btn_add_folder.pack(side="left", padx=4)

        format_tooltip_text = (
            "🎬 [지원하는 전체 비디오 및 사진 포맷 (총 30종)]\n\n"
            "• 동영상 포맷:\n"
            "  MP4, MKV, AVI, MOV, WEBM, WMV, 3GP, 3G2,\n"
            "  FLV, F4V, ASF, DIVX, MPG, MPEG, M2V, VOB,\n"
            "  TS, MTS, M2TS, TP, M4V, OGV, QT\n\n"
            "• 사진 및 모션 JPEG 포맷:\n"
            "  JPG, JPEG, JPE, MJPG, MJPEG, MJP"
        )
        WidgetToolTip(self.btn_add_files, format_tooltip_text)
        WidgetToolTip(self.btn_add_folder, format_tooltip_text)

        ttk.Button(btn_frame, text="↺ 회전/반전 ▾", style='Add.TButton', command=self.show_rotation_menu_selected).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="🗑️ 선택 삭제 (Del)", style='Danger.TButton', command=self.remove_selected).pack(side="left", padx=(10, 4))
        ttk.Button(btn_frame, text="🧹 전체 비우기", style='Danger.TButton', command=self.clear_all).pack(side="left")
        ttk.Button(btn_frame, text="🔄 완료 항목 재작업", style='Reset.TButton', command=self.reset_completed_items).pack(side="left", padx=(10, 0))
        # [v3.9] 더블클릭 비교 길이는 하단 '미리보기 길이' 값으로 통일되었다.
        if DND_SUPPORTED:
            ttk.Label(btn_frame, text="※ 파일/폴더를 아래 목록으로 드래그해서 추가할 수 있습니다.",
                      style='Sub.TLabel').pack(side="right")

        tree_container = ttk.Frame(frame_queue)
        tree_container.pack(fill="both", expand=True)

        columns = ("chk", "name", "orig_codec", "orig_res", "rotate", "orig_bitrate", "orig_size",
                   "crf_sel", "result_codec", "size_info", "ratio_info", "status")
        self.tree = ttk.Treeview(tree_container, columns=columns, show="headings",
                                 selectmode="extended", height=5)

        headers = {
            "chk": ("☐", 26, "center"),
            "name": ("파일명", 155, "w"), "orig_codec": ("원본 코덱", 65, "center"),
            "orig_res": ("원본 해상도", 70, "center"),
            "rotate": ("회전/반전 ▾", 75, "center"),
            "orig_bitrate": ("원본 비트레이트", 75, "center"),
            "orig_size": ("원본 크기", 65, "e"),
            "crf_sel": ("목표 화질 ▾", 105, "center"),
            "result_codec": ("결과 코덱 ▾", 95, "center"),
            "size_info": ("예상 파일 크기", 95, "e"),
            "ratio_info": ("예상 압축율", 85, "center"),
            "status": ("상태 및 남은 시간", 150, "center"),
        }
        for col, (txt, width, anchor) in headers.items():
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=width, anchor=anchor, minwidth=30 if col == 'chk' else 60)

        self.tree.tag_configure('processing', background='#dbeafe', foreground='#1d4ed8',
                                font=("맑은 고딕", 9, "bold"))
        self.tree.tag_configure('done', background='#f0fdf4', foreground='#15803d')
        self.tree.tag_configure('error', background='#fef2f2', foreground='#b91c1c')

        # [v4.5] 예상 결과 용량에 따른 색상 게이지 태그 (빨강 / 주황 / 노랑 / 연두 / 녹색)
        self.tree.tag_configure('gauge_red', background='#fee2e2', foreground='#991b1b')     # 원본 용량 대비 증가 (빨간색)
        self.tree.tag_configure('gauge_orange', background='#ffedd5', foreground='#c2410c')  # 5% 이하 감소 (주황계열)
        self.tree.tag_configure('gauge_yellow', background='#fef9c3', foreground='#854d0e')  # 30% 정도 감소 (노랑계열)
        self.tree.tag_configure('gauge_lime', background='#ecfccb', foreground='#3f6212')    # 30%~50% 감소 (연두 범위)
        self.tree.tag_configure('gauge_green', background='#dcfce7', foreground='#15803d')   # 50% 이상 감소 (녹색 범위)

        vsb = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_container.rowconfigure(0, weight=1)
        tree_container.columnconfigure(0, weight=1)

        self.tree.bind('<Delete>', lambda e: self.remove_selected())
        self.tree.bind('<Button-1>', self.on_tree_click)
        self.tree.bind('<Double-1>', self.on_tree_double_click)
        self.tree.bind('<Button-3>', self.on_tree_right_click)     # [v4.52] 우클릭 컨텍스트 메뉴 (Win/Linux)
        self.tree.bind('<Button-2>', self.on_tree_right_click)     # [v4.52] 우클릭 컨텍스트 메뉴 (macOS)
        self.tree.bind('<<TreeviewSelect>>', self.on_tree_select)  # [v4.5] 대기열 선택 시 하단 설정 동기화
        self.tree.bind('<Motion>', self._on_tree_motion)          # [v3.4] 상세 툴팁
        self.tree.bind('<Leave>', lambda e: self._hide_crf_tooltip())
        if DND_SUPPORTED:
            self.tree.drop_target_register(DND_FILES)
            self.tree.dnd_bind('<<Drop>>', self.handle_drop)

        # 요약 패널 (고정 높이 38px 및 여유로운 상하 여백 중앙 정렬로 수치 잘림 완전 방지)
        self.frame_summary = tk.Frame(frame_queue, bg=self.CARD_BG,
                                      highlightbackground="#d1d5db", highlightthickness=1, height=38)
        self.frame_summary.pack(fill="x", pady=(5, 0))
        self.frame_summary.pack_propagate(False)

        self.summary_labels = {}
        summary_items = [
            ("count", "파일 수", "0개"),
            ("orig", "원본 총 크기", "0 MB"),
            ("duration", "전체 재생 시간", "0초"),
            ("est", "예상 총 크기", "0 MB"),
            ("ratio", "예상 절감률", "0%"),
            ("time", "남은 인코딩 시간", "0초"),
        ]
        self.frame_summary.rowconfigure(0, weight=1)
        for i, (key, title, default) in enumerate(summary_items):
            cell = tk.Frame(self.frame_summary, bg=self.CARD_BG)
            cell.grid(row=0, column=i, sticky="nsew", padx=3, pady=2)
            self.frame_summary.columnconfigure(i, weight=1, uniform="sum")
            color = self.ACCENT if key == "ratio" else ("#0284c7" if key == "duration" else ("#dc2626" if key == "time" else self.TEXT_MAIN))
            lbl = tk.Label(cell, text=f"{title}: {default}", bg=self.CARD_BG, fg=color,
                           font=("맑은 고딕", 9, "bold"), anchor="center")
            lbl.pack(fill="both", expand=True)
            self.summary_labels[key] = (lbl, title)

        # [v4.60 UX 개선] 실시간 작업 대시보드 (작업 대기열 하단 배치)
        frame_dash = ttk.LabelFrame(frame_queue, text=" 📊 실시간 작업 대시보드 ", padding=6)
        frame_dash.pack(fill="x", pady=(6, 0))

        self.lbl_stats = ttk.Label(frame_dash, text="대기 중... 파일을 추가하고 시작을 눌러주세요.",
                                   font=("맑은 고딕", 10, "bold"))
        self.lbl_stats.pack(anchor="w", pady=(0, 2))

        self.progress = ttk.Progressbar(frame_dash, mode="determinate")
        self.progress.pack(fill="x", pady=(0, 2), ipady=2)

        # [2] 하단 영역 (고정 하단 배치)
        frame_bottom = ttk.Frame(main_container)
        frame_bottom.pack(fill="x", side="bottom")

        # 인코딩 상세 설정 (grid 정렬로 누락/잘림 방지)
        frame_opts = ttk.LabelFrame(frame_bottom, text=" ⚙️ 인코딩 상세 설정 ", padding=8)
        frame_opts.pack(fill="x", pady=(0, 6))

        grid = ttk.Frame(frame_opts)
        grid.pack(fill="x")
        for c in range(6):
            grid.columnconfigure(c, weight=1 if c % 2 == 1 else 0)

        # 1행: 가속 장치 / 출력 코덱 / 출력 포맷
        ttk.Label(grid, text="가속 장치:").grid(row=0, column=0, sticky="w", pady=2, padx=(0, 4))
        self.combo_hw = ttk.Combobox(grid, values=["AMD (AMF) - 기본", "NVIDIA (NVENC)",
                                                   "Intel (QSV)", "CPU 전용 (호환성 최상)"],
                                     state="readonly", width=24)
        if self.detected_gpu_vendor == "NVIDIA":
            self.combo_hw.current(1)
        elif self.detected_gpu_vendor == "Intel":
            self.combo_hw.current(2)
        elif self.detected_gpu_vendor == "AMD":
            self.combo_hw.current(0)
        else:
            self.combo_hw.current(3)
        self.combo_hw.grid(row=0, column=1, sticky="ew", pady=2, padx=(0, 16))
        self.combo_hw.bind("<<ComboboxSelected>>", self.on_quality_setting_change)

        ttk.Label(grid, text="출력 코덱:").grid(row=0, column=2, sticky="w", pady=2, padx=(0, 4))
        self.combo_codec = ttk.Combobox(grid, values=[
            "AV1 (차세대 초고압축, 추천)",
            "H.265/HEVC (고압축)",
            "H.264 (표준, 호환성)",
            "VP9 (웹 호환성)",
            "MKV 방식 (Matroska - 자막/다중트랙 보존)",
            "MP3 (오디오 전용 추출)"
        ], state="readonly", width=34)
        self.combo_codec.current(0)
        self.combo_codec.grid(row=0, column=3, sticky="ew", pady=2, padx=(0, 16))
        self.combo_codec.bind("<<ComboboxSelected>>", self.on_codec_change)

        ttk.Label(grid, text="출력 포맷:").grid(row=0, column=4, sticky="w", pady=2, padx=(0, 4))
        self.combo_format = ttk.Combobox(grid, values=["MP4 (.mp4)", "MKV (.mkv)", "MP3 (.mp3)"],
                                         state="readonly", width=14)
        self.combo_format.current(1)  # [v4.60] 기본 출력 포맷: MKV (.mkv)
        self.combo_format.grid(row=0, column=5, sticky="ew", pady=2)
        self.combo_format.bind("<<ComboboxSelected>>", self.on_format_change)

        # 2행: 해상도 / 프레임 / 오디오
        ttk.Label(grid, text="해상도 변경:").grid(row=1, column=0, sticky="w", pady=2, padx=(0, 4))
        self.combo_res = ttk.Combobox(grid, values=["원본 유지", "3840x2160 (UHD)",
                                                    "1920x1080 (FHD)", "1280x720 (HD)",
                                                    "854x480 (SD)", "✏️ 사용자 직접 입력..."],
                                      state="normal", width=24)
        self.combo_res.current(0)
        self.combo_res.grid(row=1, column=1, sticky="ew", pady=2, padx=(0, 16))
        self.combo_res.bind("<<ComboboxSelected>>", self.on_quality_setting_change)
        self.combo_res.bind("<Return>", self.on_quality_setting_change)

        ttk.Label(grid, text="프레임(FPS):").grid(row=1, column=2, sticky="w", pady=2, padx=(0, 4))
        self.combo_fps = ttk.Combobox(grid, values=["원본 유지", "60", "30", "24"],
                                      state="readonly", width=34)
        self.combo_fps.current(0)
        self.combo_fps.grid(row=1, column=3, sticky="ew", pady=2, padx=(0, 16))
        self.combo_fps.bind("<<ComboboxSelected>>", self.on_quality_setting_change)

        ttk.Label(grid, text="오디오 품질:").grid(row=1, column=4, sticky="w", pady=2, padx=(0, 4))
        self.combo_audio = ttk.Combobox(grid, values=[
            "128k (표준 - 기본값)", "192k (고음질)", "96k (절약)",
            "원본 복사 (Copy)", "🔇 음소거 (소리 제거)"
        ], state="readonly", width=18)
        self.combo_audio.current(0)
        self.combo_audio.grid(row=1, column=5, sticky="ew", pady=2)
        self.combo_audio.bind("<<ComboboxSelected>>", self.update_estimations)

        # ── 3행: 저장 위치 설정 (드롭다운 + 경로 입력창) [v4.60 UI 개선] ─────
        row_out = ttk.Frame(frame_opts)
        row_out.pack(fill="x", pady=(6, 2))

        ttk.Label(row_out, text="저장 위치:").pack(side="left", padx=(0, 6))

        self.combo_output_mode = ttk.Combobox(
            row_out, values=[
                "📁 원본 폴더와 동일 (기본)",
                "📂 원본 폴더 내 서브폴더 (/압축_결과)",
                "🎯 지정 폴더 (하위 폴더 구조 유지)"
            ],
            state="readonly", width=32)
        m_cur = self.output_mode.get()
        self.combo_output_mode.current(0 if m_cur == 'source' else (1 if m_cur == 'subfolder' else 2))
        self.combo_output_mode.pack(side="left", padx=(0, 8))
        self.combo_output_mode.bind("<<ComboboxSelected>>", self.on_output_mode_change)

        self.entry_outdir = ttk.Entry(row_out, state="readonly")
        self.entry_outdir.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.btn_outdir = ttk.Button(row_out, text="찾아보기...", width=10,
                                     command=self.choose_output_dir)
        self.btn_outdir.pack(side="left")

        # ── 3-2행: 저장 및 작업 옵션 체크박스 모음 [v4.60 '저장 위치:' 하위 들여쓰기 정렬] ───
        row_opts_chk = ttk.Frame(frame_opts)
        # ── 3-2행: 저장 및 작업 옵션 체크박스 모음 (2줄로 개행 정렬) ───
        row_opts_chk1 = ttk.Frame(frame_opts)
        row_opts_chk1.pack(fill="x", pady=(2, 2), padx=(72, 0))

        # [v4.65g] 파일명 저장 모드 드롭다운
        ttk.Label(row_opts_chk1, text="파일명/파일정보:").pack(side="left", padx=(0, 2))
        self.combo_filename_mode = ttk.Combobox(
            row_opts_chk1, textvariable=self.filename_mode_var,
            values=[
                "새로운 파일명 사용(기존명칭+인코딩 정보)",
                "기존 파일명 유지하기(파일명만)",
                "기존 파일명 + 파일 정보 유지하기",
                "기존 파일명 + 파일 정보 유지 + 영상과 자막 분리"
            ], state="readonly", width=28)
        self.combo_filename_mode.pack(side="left", padx=(0, 16))
        self.combo_filename_mode.current(0)
        self.combo_filename_mode.bind("<<ComboboxSelected>>", self.update_estimations)
        WidgetToolTip(self.combo_filename_mode,
            "💾 [파일명 저장 모드 설명]\n\n"
            "• 새로운 파일명 사용(기존명칭+인코딩 정보): 압축 코덱/해상도/CRF 정보를\n  파일명에 추가 (예: 여행_HEVC_1080p_CRF28.mkv)\n\n"
            "• 기존 파일명 유지하기(파일명만): 원본 파일명을\n  그대로 사용 (확장자만 변경)\n\n"
            "• 기존 파일명 + 파일 정보 유지하기: 원본 파일명 + 원본의\n  생성시각/촬영정보/Exif 메타데이터를 복원\n\n"
            "• 기존 파일명 + 파일 정보 유지 + 영상과 자막 분리: 원본 파일명 & Exif 메타데이터 유지 +\n  영상 내 자막을 분리 추출하여 동일 폴더에 .srt 파일로 자동 저장")

        self.chk_delorig = ttk.Checkbutton(row_opts_chk1, text="🗑️ 작업 완료 후 원본 삭제",
                                           variable=self.delete_orig_file)
        self.chk_delorig.pack(side="left", padx=(0, 16))

        self.chk_skipinfo = ttk.Checkbutton(row_opts_chk1, text="📄 txt 리포트 파일 생성하지 않기",
                                            variable=self.skip_info_file)
        self.chk_skipinfo.pack(side="left", padx=(0, 16))

        self.chk_skipdup = ttk.Checkbutton(row_opts_chk1, text="🔍 중복 파일 자동 제외",
                                           variable=self.skip_duplicate_files,
                                           command=lambda: self.filter_duplicates_in_queue(show_msg=True))
        self.chk_skipdup.pack(side="left", padx=(0, 16))
        WidgetToolTip(self.chk_skipdup, "💡 [동일 영상/사진 중복 제외]\n\n대기열에 있는 파일 중 내용(해시)이 완전히 동일한 중복 파일이 있을 경우, 1개만 남기고 자동으로 체크 해제(☐)하여 중복 인코딩/병합을 방지합니다.")

        self.lbl_photo_option = ttk.Label(row_opts_chk1, text="📷 정지 사진:")
        self.lbl_photo_option.pack(side="left", padx=(8, 4))
        self.combo_photo_option = ttk.Combobox(
            row_opts_chk1, textvariable=self.photo_option_var,
            values=[
                "모션 JPEG만 작업(음성 포함)",
                "1초 슬라이드 영상 생성",
                "3초 슬라이드 영상 생성",
                "5초 슬라이드 영상 생성"
            ], state="disabled", width=22)
        self.combo_photo_option.pack(side="left")
        self.combo_photo_option.current(0)
        self.combo_photo_option.bind("<<ComboboxSelected>>", self.update_estimations)
        WidgetToolTip(self.combo_photo_option,
            "💡 [정지 사진(JPG) 및 모션 JPEG 처리]\n\n"
            "• 모션 JPEG만 작업: 음성 포함 모션 JPEG만 인코딩,\n  음성 없는 일반 사진은 자동 제외\n"
            "• 1초/3초/5초 슬라이드: 정지 사진을 지정한\n  초 동안 재생되는 동영상으로 전환\n\n"
            "※ 대기열에 이미지(JPG/JPEG) 파일이\n  있을 때만 활성화됩니다.")

        # ── 3-3행: 동영상 병합 옵션 개행 배치 (잘림 방지) ───
        row_opts_chk2 = ttk.Frame(frame_opts)
        row_opts_chk2.pack(fill="x", pady=(2, 4), padx=(72, 0))

        self.chk_merge = ttk.Checkbutton(row_opts_chk2, text="🔗 대기열 순서대로 하나로 병합",
                                         variable=self.merge_mode,
                                         command=self.on_merge_mode_toggle)
        self.chk_merge.pack(side="left")
        WidgetToolTip(self.chk_merge, "💡 작업 대기열에서 체크(☑) 표시된 영상들을 위에서 아래 순서대로 1개의 통합 파일로 연결하여 병합합니다.")

        self.combo_merge_fit = ttk.Combobox(
            row_opts_chk2, values=[
                "늘리기 (Stretch - 비율 무시 화면 꽉 채우기)",
                "자동 맞춤 (Contain/Fit - 비율유지+여백)",
                "꽉 채우기 (Cover/Fill - 비율유지+잘라내기)",
                "가운데 정렬 (Center - 원본 크기 중앙배치)"
            ], state="disabled", width=36)
        self.combo_merge_fit.current(1)
        self.combo_merge_fit.pack(side="left", padx=(6, 0))
        self.combo_merge_fit.bind("<<ComboboxSelected>>", self.on_merge_fit_change)

        self.btn_merge_help = ttk.Button(row_opts_chk2, text="❓ 도움말", width=8,
                                         state="disabled", command=self.show_merge_fit_help)
        self.btn_merge_help.pack(side="left", padx=(4, 0))

        self.chk_merge_caption = ttk.Checkbutton(row_opts_chk2, text="🏷️ 파일별 파일명 자막 표시",
                                                 variable=self.merge_caption_mode,
                                                 command=self._on_caption_mode_toggle)
        self.chk_merge_caption.pack(side="left", padx=(10, 0))
        WidgetToolTip(self.chk_merge_caption, "💡 각 파일 구간 시작 시 파일명을\n선택한 자막 테마로 화면에 표시합니다.")

        self.combo_caption_duration = ttk.Combobox(
            row_opts_chk2, textvariable=self.caption_duration_var,
            values=["표시 안함", "사용자 지정", "계속 (재생 내내)"],
            state="disabled", width=13)
        self.combo_caption_duration.pack(side="left", padx=(4, 0))
        self.combo_caption_duration.bind("<<ComboboxSelected>>", self._on_caption_duration_change)
        WidgetToolTip(self.combo_caption_duration,
            "💡 [파일명 자막 표시 시간]\n\n"
            "• 표시 안함: 자막을 표시하지 않음\n"
            "• 사용자 지정: 옆 칸에 입력한 초 동안 표시\n"
            "• 계속 (재생 내내): 파일 재생 전체 구간 표시")

        self.spin_caption_sec = ttk.Spinbox(
            row_opts_chk2, from_=1, to=60, width=3,
            textvariable=self.caption_custom_sec, state="disabled")
        self.spin_caption_sec.pack(side="left", padx=(2, 0))
        ttk.Label(row_opts_chk2, text="초").pack(side="left", padx=(1, 4))

        self.combo_caption_theme = ttk.Combobox(
            row_opts_chk2, textvariable=self.caption_theme_var,
            values=list(CAPTION_THEMES.keys()),
            state="disabled", width=22)
        self.combo_caption_theme.pack(side="left")

        self.btn_caption_theme_preview = ttk.Button(
            row_opts_chk2, text="👁️ 미리보기", width=10,
            state="disabled", command=self.show_caption_theme_preview_dialog)
        self.btn_caption_theme_preview.pack(side="left", padx=(4, 0))
        WidgetToolTip(self.btn_caption_theme_preview, "💡 [자막 테마 예시 미리보기]\n\n각 자막 버튼 테마의 실시간 예시 디자인을 확인하고 원하시는 테마를 고를 수 있습니다.")

        # [v4.649] 자막 글자 색상 사용자 선택 팔레트 버튼 추가
        self.custom_caption_color = "#ffffff"
        self.btn_caption_color = ttk.Button(
            row_opts_chk2, text="🎨 글자 색상", width=10,
            state="disabled", command=self.pick_caption_color)
        self.btn_caption_color.pack(side="left", padx=(4, 0))
        WidgetToolTip(self.btn_caption_color, "💡 [자막 글자 색상 팔레트]\n\n원하시는 자막 글자 색상을 직접 팔레트에서 선택할 수 있습니다.")

        merge_tip_text = (
            "💡 비디오 병합 화면 맞춤 모드 안내:\n\n"
            "• 늘리기 (Stretch)  : 원본 비율과 상관없이 설정한 해상도(사용자 입력/변경 해상도) 크기 전체로 늘립니다. (기본 설정)\n"
            "• 자동 맞춤 (Contain): 원본 비율을 유지하며 설정 해상도 안에 맞추고 남은 공간은 여백(블랙바) 처리합니다.\n"
            "• 꽉 채우기 (Cover)  : 여백 없이 설정 해상도를 꽉 채우도록 중앙 기준 확대 후 잘라냅니다.\n"
            "• 가운데 정렬 (Center): 비디오 크기를 조절하지 않고 설정 해상도 캔버스 중앙에 배치합니다."
        )
        WidgetToolTip(self.combo_merge_fit, merge_tip_text)
        WidgetToolTip(self.btn_merge_help, merge_tip_text)

        self._refresh_outdir_widgets()

        # ── 4행: 화질 선택 라벨 및 자동화질/미리보기 옵션 ───────────────
        row3_top = ttk.Frame(frame_opts)
        row3_top.pack(fill="x", pady=(2, 0))

        # 우측 영역: 미리보기 길이 지정 및 미리보기 버튼 (항상 최우선 고정 배치)
        right_box = ttk.Frame(row3_top)
        right_box.pack(side="right", anchor="e", padx=(10, 0))

        preview_len_row = ttk.Frame(right_box)
        preview_len_row.pack(anchor="e", fill="x", pady=(1, 0))
        ttk.Label(preview_len_row, text="미리보기 길이:").pack(side="left")
        try:
            self.spin_preview_duration = ttk.Spinbox(
                preview_len_row, from_=1, to=600, width=5,
                textvariable=self.preview_duration_var)
        except AttributeError:
            self.spin_preview_duration = tk.Spinbox(
                preview_len_row, from_=1, to=600, width=5,
                textvariable=self.preview_duration_var)
        self.spin_preview_duration.pack(side="left", padx=(4, 2))
        ttk.Label(preview_len_row, text="초 (1~600)").pack(side="left")

        self.btn_preview = ttk.Button(preview_len_row, text="🎞️ 샘플링하여 미리보기",
                                      style='Preview.TButton', command=self.start_preview)
        self.btn_preview.pack(side="left", padx=(10, 0))

        # 좌측 영역: 화질(CRF) || 화질 기준: [드롭다운] || [2줄 메시지] [중지버튼]
        left_info_box = ttk.Frame(row3_top)
        left_info_box.pack(side="left", anchor="w")

        # 1) 화질(CRF) 라벨 및 현재 값 표시
        ttk.Label(left_info_box, text="화질(CRF):").pack(side="left", anchor="w")
        self.crf_var = tk.IntVar(value=35)
        self.lbl_crf_val = tk.Label(left_info_box, text="35 · ⭐ 동일화질 균형추천 (용량 ~65% 절감)", anchor="w",
                                    bg=self.BG_COLOR, fg="#166534",
                                    font=("맑은 고딕", 10, "bold"))
        self.lbl_crf_val.pack(side="left", padx=(4, 2))

        # 2) 첫 번째 ' || ' 구분자
        ttk.Label(left_info_box, text=" || ").pack(side="left")

        # 3) 화질 기준: 라벨 및 드롭다운
        ttk.Label(left_info_box, text="전체 파일에 자동 화질 적용:").pack(side="left")
        self.auto_quality_profile_var = tk.StringVar(value="동일 화질")
        self.combo_auto_quality = ttk.Combobox(
            left_info_box, textvariable=self.auto_quality_profile_var,
            values=self.AUTO_QUALITY_PROFILES, state="readonly", width=12)
        self.combo_auto_quality.pack(side="left", padx=(4, 2))
        self.combo_auto_quality.bind("<<ComboboxSelected>>", self.on_auto_quality_profile_change)

        self.precise_sampling_var = tk.BooleanVar(value=False)
        self.chk_precise_sampling = tk.Checkbutton(
            left_info_box, text="샘플링하여 정밀 추천", variable=self.precise_sampling_var,
            command=self.on_auto_quality_profile_change, bg=self.BG_COLOR
        )
        self.chk_precise_sampling.pack(side="left", padx=(2, 4))

        # 4) 두 번째 ' || ' 구분자
        ttk.Label(left_info_box, text=" || ").pack(side="left")

        # 5) 2줄 상태 메시지 표시 라벨
        self.lbl_auto_quality_status = tk.Label(
            left_info_box, text="자동화질 준비", bg=self.BG_COLOR, fg="#059669",
            font=("맑은 고딕", 8, "bold"), anchor="w", justify="left", wraplength=260)
        self.lbl_auto_quality_status.pack(side="left")

        # 6) 중지 버튼
        self.btn_cancel_precise = ttk.Button(
            left_info_box, text="⏹️ 중지", width=6,
            command=self.cancel_precise_quality_analysis)

        # ── 5행: 슬라이더 세로 폭 슬림화 (위/아래 여백 최소화) ──────
        slider_box = ttk.Frame(frame_opts)
        slider_box.pack(fill="x", pady=(1, 1))

        # 슬라이더 상단 캔버스 (높이 34px로 확장하여 2줄 텍스트 잘림 완전 해결)
        self.crf_top_canvas = tk.Canvas(slider_box, height=34, bg=self.BG_COLOR, highlightthickness=0)
        self.crf_top_canvas.pack(fill="x")

        self.scale_crf = tk.Scale(slider_box, from_=18, to=63, orient="horizontal",
                                  variable=self.crf_var, bg=self.BG_COLOR, showvalue=0,
                                  sliderlength=16, bd=0, highlightthickness=0,
                                  command=self.on_crf_change)
        self.scale_crf.pack(fill="x")

        # 마커 캔버스 (높이 36px로 축소 및 여백 제거)
        self.crf_marker_canvas = tk.Canvas(slider_box, height=36, bg=self.BG_COLOR,
                                           highlightthickness=0)
        self.crf_marker_canvas.pack(fill="x")
        self.crf_marker_canvas.bind('<Configure>', self.draw_crf_markers)
        self.crf_top_canvas.bind('<Configure>', self.draw_crf_markers)

        # ── 6행: 퀵 프로필 칩 & 실행/취소 버튼 통합 행 [frame_opts 내부 안전 배치 - 잘림 원천 차단] ───
        self.preset_chips_frame = ttk.Frame(frame_opts, padding=(0, 6, 0, 2))
        self.preset_chips_frame.pack(fill="x")

        self.chips_left_box = ttk.Frame(self.preset_chips_frame)
        self.chips_left_box.pack(side="left", anchor="w")
        self.refresh_preset_chips()

        # 오른쪽 끝: 일괄 압축 시작 & 작업 취소 & (병합 모드 시) 저장위치/파일 열기 버튼
        frame_action = ttk.Frame(self.preset_chips_frame)
        frame_action.pack(side="right", anchor="e")

        self.btn_open_out_dir = ttk.Button(
            frame_action, text="📂 저장위치 열기",
            command=self.open_last_output_dir)
        WidgetToolTip(self.btn_open_out_dir, "💡 마지막으로 저장된 폴더를 탐색기에서 엽니다.")

        self.btn_open_out_file = ttk.Button(
            frame_action, text="🎬 저장파일 열기",
            command=self.open_last_output_file)
        WidgetToolTip(self.btn_open_out_file, "💡 마지막으로 저장된 출력 파일을 기본 플레이어로 재생합니다.")

        self.btn_start = ttk.Button(frame_action, text="▶ 작업 시작",
                                    style='Primary.TButton', command=self.start_batch)
        self.btn_start.pack(side="left", padx=(0, 6), ipady=2)

        self.btn_cancel = ttk.Button(frame_action, text="■ 작업 취소", style='Cancel.TButton',
                                     state="disabled", command=self.cancel_batch)
        self.btn_cancel.pack(side="left", padx=(0, 6), ipady=2)

        self.refresh_ffmpeg_status()
        self.auto_select_hw_accelerator_for_codec()
        self.update_merge_fit_state()

    # ==================================================================
    #  [v3.0] 저장 위치 / 파일명 규칙
    # ==================================================================
    def _refresh_outdir_widgets(self):
        """저장 위치 모드에 따라 경로 입력창/찾아보기/파일명 체크박스 활성화 갱신"""
        mode = self.output_mode.get()
        custom = (mode == 'custom')
        subfolder = (mode == 'subfolder')
        state_btn = "normal" if custom else "disabled"
        self.btn_outdir.config(state=state_btn)
        self.combo_filename_mode.config(state="readonly")
        self.entry_outdir.config(state="normal")
        self.entry_outdir.delete(0, "end")
        if custom and self.output_dir:
            self.entry_outdir.insert(0, self.output_dir)
        elif custom:
            self.entry_outdir.insert(0, "(저장 폴더를 선택해주세요)")
        elif subfolder:
            self.entry_outdir.insert(0, "각 원본 폴더 내부 하위 폴더 (/압축_결과)에 저장됩니다.")
        else:
            self.entry_outdir.insert(0, "각 원본 파일과 같은 폴더에 저장됩니다.")
        self.entry_outdir.config(state="readonly")

    def on_output_mode_change(self, *args):
        val = self.combo_output_mode.get()
        if "서브폴더" in val:
            self.output_mode.set('subfolder')
        elif "지정" in val:
            self.output_mode.set('custom')
            if not self.output_dir:
                self.choose_output_dir()
                if not self.output_dir:
                    self.output_mode.set('source')
                    self.combo_output_mode.current(0)
        else:
            self.output_mode.set('source')
        self._refresh_outdir_widgets()
        self.update_estimations()

    def update_merge_fit_state(self):
        """[v4.55/v4.65b] 병합 모드가 체크되어 있거나, 해상도가 '원본 유지'가 아닌 다른 해상도로 선택/입력된 경우 병합 맞춤 드롭다운 활성화"""
        if not hasattr(self, 'combo_merge_fit') or not self.combo_merge_fit:
            return

        res = self.combo_res.get() if hasattr(self, 'combo_res') else "원본 유지"
        is_merge = self.merge_mode.get() if hasattr(self, 'merge_mode') else False
        is_res_changed = bool(res and "원본" not in res and "유지" not in res and "사용자" not in res and "직접" not in res)

        enabled = is_merge or is_res_changed
        self.combo_merge_fit.config(state="readonly" if enabled else "disabled")
        if hasattr(self, 'btn_merge_help') and self.btn_merge_help:
            self.btn_merge_help.config(state="normal" if enabled else "disabled")

        # [v4.65b] 저장위치 열기 / 저장파일 열기 버튼: '하나로 병합' 모드일 때만 작업 실행 버튼 옆에 활성화하여 표시
        if hasattr(self, 'btn_open_out_dir') and self.btn_open_out_dir:
            if is_merge:
                self.btn_open_out_dir.pack(side="left", padx=(0, 6), ipady=2)
                self.btn_open_out_file.pack(side="left", padx=(0, 6), ipady=2)
            else:
                self.btn_open_out_dir.pack_forget()
                self.btn_open_out_file.pack_forget()

    def _on_caption_mode_toggle(self):
        """[v4.631] 파일명 자막 표시 체크박스 토글 → 관련 콤보/스핀 활성화 제어"""
        enabled = self.merge_caption_mode.get()
        if enabled:
            self.combo_caption_duration.config(state="readonly")
            self.combo_caption_theme.config(state="readonly")
            if hasattr(self, 'btn_caption_theme_preview') and self.btn_caption_theme_preview:
                self.btn_caption_theme_preview.config(state="normal")
            if hasattr(self, 'btn_caption_color') and self.btn_caption_color:
                self.btn_caption_color.config(state="normal")
            if self.caption_duration_var.get() == "표시 안함":
                self.caption_duration_var.set("계속")
            self._on_caption_duration_change()
        else:
            self.combo_caption_duration.config(state="disabled")
            self.combo_caption_theme.config(state="disabled")
            if hasattr(self, 'btn_caption_theme_preview') and self.btn_caption_theme_preview:
                self.btn_caption_theme_preview.config(state="disabled")
            if hasattr(self, 'btn_caption_color') and self.btn_caption_color:
                self.btn_caption_color.config(state="disabled")
            self.spin_caption_sec.config(state="disabled")

    def _on_caption_duration_change(self, event=None):
        """[v4.631] 자막 시간 드롭다운 변경 → 스핀박스 활성화/비활성화"""
        mode = self.caption_duration_var.get()
        if mode == "사용자 지정":
            self.spin_caption_sec.config(state="normal")
        else:
            self.spin_caption_sec.config(state="disabled")

    def on_merge_mode_toggle(self):
        """[v4.60] 비디오 병합 모드 토글 및 콤보박스/도움말 활성화 제어"""
        enabled = self.merge_mode.get()
        self.update_merge_fit_state()

        if enabled:
            # [v4.60 UX 개선] 목록에서 아무것도 선택/체크되지 않았을 경우 모든 대기 항목 자동 체크
            checked_count = sum(1 for item in self.file_list if item.get('checked', False))
            if checked_count == 0 and self.file_list:
                for item in self.file_list:
                    item['checked'] = True
                    self.tree.set(item['id'], "chk", "☑")
                self.update_summary()

            messagebox.showinfo(
                "🔗 1개 파일로 병합 모드 안내",
                "대기열 목록에서 체크(☑)된 영상들이 목록 위에서 아래 순서대로 1개의 통합 영상으로 병합됩니다.\n\n"
                "💡 [병합 맞춤 모드 안내]\n"
                "오른쪽 드롭다운에서 지정/변경한 해상도에 영상들을 배치할 방식을 선택할 수 있습니다:\n"
                "• 늘리기 (Stretch)  : 비율 무시 설정 해상도에 맞게 화면 전체 늘림 [기본 설정]\n"
                "• 자동 맞춤 (Contain): 원본 비율 유지 + 여백(블랙바) 생성\n"
                "• 꽉 채우기 (Cover)  : 여백 없이 꽉 채움 + 화면 잘라내기\n"
                "• 가운데 정렬 (Center): 원본 크기 그대로 중앙 배치\n\n"
                "※ 해상도 변경 및 프레임(FPS) 옵션을 원하시는 규격으로 설정해 주시기 바랍니다.", parent=self.root)
        self.update_estimations()

    def show_merge_fit_help(self):
        """[v4.60] 병합 모드 설명 창 팝업"""
        help_msg = (
            "🎬 [비디오 병합 화면 맞춤 모드 상세 설명]\n\n"
            "1. ↔️ 늘리기 (Stretch / Distort) - [기본 설정]\n"
            "   - 원본 비율과 상관없이 설정한 해상도 크기 전체에 맞춰 가로/세로를 꽉 채워 늘립니다.\n"
            "   - 블랙바 여백이나 화면 잘림 없이 지정한 해상도 규격으로 정확히 출력됩니다.\n\n"
            "2. 📐 자동 맞춤 (Contain / Fit)\n"
            "   - 원본 동영상의 비율을 그대로 보존하면서 설정한 해상도 안에 맞춥니다.\n"
            "   - 비율이 다른 남은 공간은 검은색 여백(블랙바)으로 깔끔하게 처리됩니다.\n\n"
            "3. 🖼️ 꽉 채우기 (Cover / Fill)\n"
            "   - 여백(블랙바) 없이 화면 전체를 꽉 채웁니다.\n"
            "   - 화면 비율이 맞지 않는 상하 또는 좌우 영역은 중앙을 기준으로 자릅니다(Crop).\n\n"
            "4. 🎯 가운데 정렬 (Center / Original)\n"
            "   - 동영상의 크기를 변경하지 않고 설정한 해상도 캔버스 중앙에 배치합니다.\n"
            "   - 해상도가 작은 영상은 중앙에 작게 보이고 큰 영상은 중앙 부위만 보입니다."
        )
        messagebox.showinfo("🔗 병합 화면 맞춤 모드 설명", help_msg, parent=self.root)

    def pick_caption_color(self):
        """[v4.649] 자막 글자 색상 선택 팔레트 팝업 띄우기"""
        from tkinter import colorchooser
        cur = getattr(self, 'custom_caption_color', '#ffffff')
        color = colorchooser.askcolor(title="🎨 자막 글자 색상 선택", initialcolor=cur, parent=self.root)
        if color and color[1]:
            self.custom_caption_color = color[1]
            messagebox.showinfo("🎨 자막 색상 지정 완료", f"자막 글자 색상이 '{color[1]}' (으)로 지정되었습니다.", parent=self.root)

    def show_caption_theme_preview_dialog(self):
        """[v4.645] 파일명 자막 둥근 알약 버튼(Pill Button) 테마 예시를 시각적으로 보여주는 미리보기 창"""
        dlg = tk.Toplevel(self.root)
        dlg.title("🎨 파일명 자막 버튼 테마 예시 미리보기")
        dlg.geometry("760x600")
        dlg.minsize(660, 480)
        dlg.transient(self.root)
        dlg.grab_set()

        header_frame = ttk.Frame(dlg, padding=12)
        header_frame.pack(fill="x")

        title_lbl = ttk.Label(
            header_frame,
            text="🎨 파일명 자막 둥근 알약 버튼(Pill Button) 테마 미리보기",
            font=("Malgun Gothic", 12, "bold"),
            foreground="#0284c7"
        )
        title_lbl.pack(anchor="w")

        info_lbl = ttk.Label(
            header_frame,
            text="영상 속 파일명 자막의 디자인 예시입니다. 원하시는 테마의 [선택하기] 버튼을 누르면 즉시 적용됩니다.",
            font=("Malgun Gothic", 9),
            foreground="#64748b"
        )
        info_lbl.pack(anchor="w", pady=(4, 0))

        container = ttk.Frame(dlg, padding=12)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, bg="#0f172a", highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def select_theme(t_name):
            self.caption_theme_var.set(t_name)
            messagebox.showinfo("자막 테마 변경", f"파일명 자막 테마가 '{t_name}'(으)로 적용되었습니다.", parent=dlg)
            dlg.destroy()

        current_theme = self.caption_theme_var.get()

        for t_name, t_info in CAPTION_THEMES.items():
            card = ttk.Frame(scroll_frame, padding=8)
            card.pack(fill="x", pady=6, padx=6)

            is_selected = (t_name == current_theme)
            header_str = f"★ {t_name} (현재 적용중)" if is_selected else t_name

            lbl_name = ttk.Label(
                card, text=header_str,
                font=("Malgun Gothic", 10, "bold"),
                foreground="#0284c7" if is_selected else "#334155"
            )
            lbl_name.pack(anchor="w")

            lbl_desc = ttk.Label(card, text=t_info['desc'], font=("Malgun Gothic", 8), foreground="#64748b")
            lbl_desc.pack(anchor="w", pady=(2, 4))

            cv = tk.Canvas(card, width=620, height=70, bg=t_info.get('canvas_bg', '#1e293b'), highlightthickness=0)
            cv.pack(anchor="w")

            raw_boxc = t_info['boxcolor'].split('@')[0]
            if raw_boxc == 'black':
                bg_c = '#0f172a'
            elif raw_boxc == 'white':
                bg_c = '#ffffff'
            else:
                bg_c = raw_boxc

            border_c = t_info['bordercolor']
            try:
                border_w = int(float(t_info['borderw']))
            except (ValueError, TypeError):
                border_w = 2

            font_c = t_info['fontcolor']
            sample_text = "🏷️ 2026_가족추억_01.mp4"

            rx1, ry1, rx2, ry2 = 340, 15, 600, 55
            rad = 18
            d = rad * 2

            cv.create_arc(rx1, ry1, rx1+d, ry1+d, start=90, extent=90, fill=bg_c, outline="")
            cv.create_arc(rx2-d, ry1, rx2, ry1+d, start=0, extent=90, fill=bg_c, outline="")
            cv.create_arc(rx2-d, ry2-d, rx2, ry2, start=270, extent=90, fill=bg_c, outline="")
            cv.create_arc(rx1, ry2-d, rx1+d, ry2, start=180, extent=90, fill=bg_c, outline="")
            cv.create_rectangle(rx1+rad, ry1, rx2-rad, ry2, fill=bg_c, outline="")
            cv.create_rectangle(rx1, ry1+rad, rx2, ry2-rad, fill=bg_c, outline="")

            if border_w > 0:
                cv.create_arc(rx1, ry1, rx1+d, ry1+d, start=90, extent=90, style="arc", outline=border_c, width=border_w)
                cv.create_arc(rx2-d, ry1, rx2, ry1+d, start=0, extent=90, style="arc", outline=border_c, width=border_w)
                cv.create_arc(rx2-d, ry2-d, rx2, ry2, start=270, extent=90, style="arc", outline=border_c, width=border_w)
                cv.create_arc(rx1, ry2-d, rx1+d, ry2, start=180, extent=90, style="arc", outline=border_c, width=border_w)
                cv.create_line(rx1+rad, ry1, rx2-rad, ry1, fill=border_c, width=border_w)
                cv.create_line(rx1+rad, ry2, rx2-rad, ry2, fill=border_c, width=border_w)
                cv.create_line(rx1, ry1+rad, rx1, ry2-rad, fill=border_c, width=border_w)
                cv.create_line(rx2, ry1+rad, rx2, ry2-rad, fill=border_c, width=border_w)

            cv.create_text((rx1+rx2)/2, (ry1+ry2)/2, text=sample_text, fill=font_c, font=("Malgun Gothic", 9, "bold"))
            cv.create_text(150, 35, text="[동영상 비디오 화면]", fill="#cbd5e1", font=("Malgun Gothic", 9, "italic"))

            btn_sel = ttk.Button(card, text="✓ 이 테마 선택하기", command=lambda name=t_name: select_theme(name))
            btn_sel.pack(anchor="e", pady=(4, 0))

        btn_frame = ttk.Frame(dlg, padding=12)
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="닫기", command=dlg.destroy).pack(side="right")

    def on_merge_fit_change(self, *args):
        self.update_estimations()

    def choose_output_dir(self):
        folder = filedialog.askdirectory(title="인코딩 결과물을 저장할 폴더 선택")
        if not folder:
            self._refresh_outdir_widgets()
            return
        self.output_dir = str(Path(folder).resolve())
        self.output_mode.set('custom')
        # [v4.65g] 저장 폴더 지정 시 원본 파일명 유지 여부를 질문
        keep = messagebox.askyesno(
            "파일명 규칙",
            "저장되는 파일 이름을 '원본 파일명과 동일'하게 저장할까요?\n\n"
            "· 예  : 원본과 같은 이름으로 저장 (예: 여행영상.mp4)\n"
            "· 아니오: 압축 정보가 붙은 이름으로 저장\n"
            "        (예: 여행영상_HEVC_1920x1080_CRF28.mp4)\n\n"
            "※ 이 설정은 아래 '파일명' 드롭다운으로 언제든 세부 변경할 수 있습니다.", parent=self.root)
        if keep:
            self.filename_mode_var.set("기존 파일명 유지하기(파일명만)")
        else:
            self.filename_mode_var.set("새로운 파일명 사용(기존명칭+인코딩 정보)")
        self.keep_orig_name.set(keep)
        self._refresh_outdir_widgets()
        self.update_estimations()

    def get_target_dir(self, item=None, gui_snapshot=None):
        """항목이 저장될 폴더 계산.
        - 지정 폴더 모드 + 폴더 추가: '지정폴더/원본루트명/원본 하위경로' 구조 재현
        - 서브폴더 모드: '원본폴더/압축_결과'
        - 원본 모드: '원본폴더'"""
        if gui_snapshot:
            out_mode = gui_snapshot.get('output_mode', 'source')
            out_dir = gui_snapshot.get('output_dir', '')
        else:
            out_mode = self.output_mode.get() if hasattr(self, 'output_mode') else 'source'
            out_dir = self.output_dir if hasattr(self, 'output_dir') else ''

        if out_mode == 'custom' and out_dir:
            base = Path(out_dir)
            if item and item.get('src_root'):
                src_root_obj = Path(item['src_root'])
                root_name = self.sanitize_component(src_root_obj.name)
                if not root_name:
                    # 드라이브 루트(D:\, Z:\)나 UNC 루트(\server\share) 처리
                    root_name = self.sanitize_component(src_root_obj.drive.rstrip(':\\') or src_root_obj.stem or "root")
                parts = [root_name] if root_name else []
                rel_dir = item.get('rel_dir', '')
                if rel_dir:
                    parts.extend(self.sanitize_component(p) for p in Path(rel_dir).parts
                                 if p not in ('.', '..'))
                return base.joinpath(*parts)
            return base
        elif out_mode == 'subfolder':
            sub_name = "압축_결과"
            if item and item.get('path'):
                return Path(item['path']).resolve().parent / sub_name
            elif self.file_list and self.file_list[0].get('path'):
                return Path(self.file_list[0]['path']).resolve().parent / sub_name
            return None
        else:
            # 원본 폴더 저장 모드 (source): 파일의 실제 절대 경로 부모 디렉터리에 정확히 저장!
            if item and item.get('path'):
                return Path(item['path']).resolve().parent
            return None

    def _shorten_for_maxpath(self, full_path):
        """Windows MAX_PATH(260자) 초과 시 파일명(stem)을 자동 축약"""
        s = str(full_path)
        if os.name != 'nt' or len(s) <= 250:
            return full_path
        p = Path(s)
        room = 250 - len(str(p.parent)) - len(p.suffix) - 1
        if room < 8:
            return full_path  # 폴더 자체가 너무 깊으면 축약 불가 (사전 검사에서 안내)
        return p.parent / (p.stem[:room].rstrip(' .') + p.suffix)

    def _uniquify_output(self, full_path):
        """동일 출력 경로 충돌 시 ' (2)', ' (3)' 자동 번호 부여
        (디스크의 기존 파일 + 현재 배치에서 이미 배정된 경로 모두 검사)"""
        p = Path(full_path)
        cand = p
        n = 2
        while str(cand) in self._batch_used_outputs or cand.exists():
            cand = p.parent / f"{p.stem} ({n}){p.suffix}"
            n += 1
        self._batch_used_outputs.add(str(cand))
        return cand

    # ==================================================================
    #  코덱 선택 처리
    # ==================================================================
    def get_max_crf(self):
        """[v4.54] AV1 선택 시 코덱 규격 한계값인 63까지, 타 코덱은 50까지 CRF 범위 확장"""
        if hasattr(self, 'combo_codec') and self.combo_codec:
            codec = self.combo_codec.get()
        else:
            codec = ""
        return 63 if "AV1" in codec else 50

    def refresh_preset_chips(self):
        """[v4.54] 코덱 선택에 따른 원클릭 퀵 프로필 칩 버튼 동적 갱신"""
        target_box = getattr(self, 'chips_left_box', None) or getattr(self, 'preset_chips_frame', None)
        if not target_box:
            return
        for child in target_box.winfo_children():
            child.destroy()

        combo_val = getattr(self, 'combo_codec', None).get() if getattr(self, 'combo_codec', None) else ""
        if "MP3" in combo_val:
            ttk.Label(target_box, text="🎵 MP3 오디오 전용 추출 모드 활성화됨", font=("맑은 고딕", 9, "bold"), foreground="#0284c7").pack(side="left", padx=(0, 6))
            return

        is_av1 = "AV1" in combo_val

        if is_av1:
            chips = [
                ("💎 원본급 (28)", 28),
                ("⭐ 균형추천 (35)", 35),
                ("🚀 고강도절약 (42)", 42),
                ("📦 극강초고압축 (50)", 50),
                ("⚡ 컴팩트보관 (56)", 56),
                ("🔥 규격최댓값 (63)", 63),
            ]
        else:
            chips = [
                ("💎 최고화질 (20)", 20),
                ("⭐ 표준화질 (25)", 25),
                ("🚀 용량절약 (30)", 30),
                ("📦 고압축 (36)", 36),
                ("⚡ 최대압축 (42)", 42),
            ]

        ttk.Label(target_box, text="⚡ 퀵 프로필:", font=("맑은 고딕", 8, "bold"), foreground="#475569").pack(side="left", padx=(0, 6))
        for label, val in chips:
            btn = ttk.Button(
                target_box, text=label,
                command=lambda v=val: self.apply_preset_crf(v)
            )
            btn.pack(side="left", padx=(0, 3))

    # ------------------------------------------------------------------
    #  [v3.0] 경로/파일명 인코딩·호환성 안전화 유틸
    # ------------------------------------------------------------------
    _WIN_RESERVED_NAMES = {'CON', 'PRN', 'AUX', 'NUL',
                           *(f'COM{i}' for i in range(1, 10)),
                           *(f'LPT{i}' for i in range(1, 10))}

    def sanitize_component(self, name):
        """폴더/파일명 한 조각을 모든 OS에서 안전한 이름으로 정규화.
        - 유니코드 NFC 정규화 (macOS 등에서 온 자모 분리(NFD) 경로 교정)
        - Windows 금지 문자(<>:\"/\\|?*) 및 제어 문자 치환
        - 예약어(CON, PRN, COM1 등) 회피, 끝 공백/마침표 제거, 상위 폴더 탈출(..) 차단"""
        s = unicodedata.normalize('NFC', str(name))
        s = ''.join(('_' if (c in '<>:"/\\|?*' or ord(c) < 32) else c) for c in s)
        s = s.rstrip(' .')
        if s in ('', '.', '..'):
            s = '_'
        stem_upper = s.split('.')[0].upper()
        if stem_upper in self._WIN_RESERVED_NAMES:
            s = '_' + s
        return s
    def win32_askopenfilenames(title="비디오 및 사진 파일 선택", initialdir=None, parent_hwnd=None):
        """[v4.64] Win32 API GetOpenFileNameW를 직접 호출하여
        드롭다운 필터 라벨에 불필요한 확장자 목록((*.mp4;*.mkv...))이 자동 덧붙지 않도록
        100% 깔끔한 서식의 네이티브 대화상자를 띄운다."""
        if os.name != 'nt':
            return []

        try:
            import ctypes
            from ctypes import wintypes

            class OPENFILENAMEW(ctypes.Structure):
                _fields_ = [
                    ('lStructSize', wintypes.DWORD), ('hwndOwner', wintypes.HWND),
                    ('hInstance', wintypes.HINSTANCE), ('lpstrFilter', wintypes.LPCWSTR),
                    ('lpstrCustomFilter', wintypes.LPWSTR), ('nMaxCustFilter', wintypes.DWORD),
                    ('nFilterIndex', wintypes.DWORD), ('lpstrFile', wintypes.LPWSTR),
                    ('nMaxFile', wintypes.DWORD), ('lpstrFileTitle', wintypes.LPWSTR),
                    ('nMaxFileTitle', wintypes.DWORD), ('lpstrInitialDir', wintypes.LPCWSTR),
                    ('lpstrTitle', wintypes.LPCWSTR), ('Flags', wintypes.DWORD),
                    ('nFileOffset', wintypes.WORD), ('nFileExtension', wintypes.WORD),
                    ('lpstrDefExt', wintypes.LPCWSTR), ('lCustData', wintypes.LPARAM),
                    ('lpfnHook', wintypes.LPARAM), ('lpTemplateName', wintypes.LPCWSTR),
                    ('pvReserved', wintypes.LPVOID), ('dwReserved', wintypes.DWORD),
                    ('FlagsEx', wintypes.DWORD),
                ]

            filter_parts = [
                "🎬 모든 비디오 및 사진 지원 포맷\0*.mp4;*.mkv;*.avi;*.mov;*.webm;*.wmv;*.3gp;*.3g2;*.flv;*.f4v;*.asf;*.divx;*.mpg;*.mpeg;*.m2v;*.vob;*.ts;*.mts;*.m2ts;*.tp;*.m4v;*.ogv;*.qt;*.jpg;*.jpeg;*.jpe;*.mjpg;*.mjpeg;*.mjp",
                "🖼️ 정지 사진 (JPG/JPEG)\0*.jpg;*.jpeg;*.jpe",
                "📹 모션 JPEG (영상+음성)\0*.jpg;*.jpeg;*.jpe;*.mjpg;*.mjpeg;*.mjp",
                "🎥 동영상 파일\0*.mp4;*.mkv;*.avi;*.mov;*.webm;*.wmv;*.3gp;*.3g2;*.flv;*.f4v;*.asf;*.divx;*.mpg;*.mpeg;*.m2v;*.vob;*.ts;*.mts;*.m2ts;*.tp;*.m4v;*.ogv;*.qt",
                "📄 모든 파일 (*.*)\0*.*"
            ]
            filter_str = "\0".join(filter_parts) + "\0\0"

            buffer_size = 65536
            file_buffer = ctypes.create_unicode_buffer(buffer_size)
            file_buffer[0] = '\0'
            dir_str = str(initialdir) if initialdir else os.getcwd()

            ofn = OPENFILENAMEW()
            ofn.lStructSize = ctypes.sizeof(OPENFILENAMEW)
            ofn.hwndOwner = parent_hwnd or 0
            ofn.lpstrFilter = filter_str
            ofn.lpstrFile = ctypes.cast(file_buffer, wintypes.LPWSTR)
            ofn.nMaxFile = buffer_size
            ofn.lpstrInitialDir = dir_str
            ofn.lpstrTitle = title
            # OFN_EXPLORER(0x80000) | OFN_ALLOWMULTISELECT(0x200) | OFN_FILEMUSTEXIST(0x1000) | OFN_PATHMUSTEXIST(0x800)
            ofn.Flags = 0x00080000 | 0x00000200 | 0x00001000 | 0x00000800
            ofn.nFilterIndex = 4  # [v4.65t] 기본 선택 필터: 4번째 항목 '🎥 동영상 파일'

            if ctypes.windll.comdlg32.GetOpenFileNameW(ctypes.byref(ofn)):
                buf_str = file_buffer[:]
                null_pos = buf_str.find('\x00\x00')
                if null_pos != -1:
                    buf_str = buf_str[:null_pos]
                parts = [p for p in buf_str.split('\x00') if p]
                if not parts:
                    return []
                if len(parts) == 1:
                    return [parts[0]]
                else:
                    dir_path = parts[0]
                    return [os.path.join(dir_path, fname) for fname in parts[1:]]
        except Exception as e:
            print(f"Win32 GetOpenFileNameW 예외 발생: {e}")
        return []

    def add_files(self):
        WidgetToolTip.hide_all_tips()  # [v4.631M] 툴팁 팝업 즉시 닫기
        hwnd = None
        try:
            hwnd = self.root.winfo_id()
        except Exception:
            hwnd = None

        if os.name == 'nt':
            files = self.win32_askopenfilenames(title="비디오 및 사진 파일 선택", parent_hwnd=hwnd)
        else:
            all_pattern = " ".join(f"*{ext}" for ext in self.VIDEO_EXTS)
            video_pattern = " ".join(f"*{ext}" for ext in self.VIDEO_EXTS if ext not in ('.jpg', '.jpeg', '.jpe'))
            photo_pattern = "*.jpg *.jpeg *.jpe"
            mjpeg_pattern = "*.jpg *.jpeg *.jpe *.mjpg *.mjpeg *.mjp"

            files = filedialog.askopenfilenames(
                title="비디오 및 사진 파일 선택",
                filetypes=[
                    ("🎥 동영상 파일 (동영상만)", video_pattern),
                    ("🎬 모든 비디오 및 사진 지원 포맷 (전체)", all_pattern),
                    ("🖼️ 정지 사진 (JPG/JPEG)", photo_pattern),
                    ("📹 모션 JPEG (영상+음성)", mjpeg_pattern),
                    ("📄 모든 파일 (*.*)", "*.*")
                ]
            )

        if files:
            self.process_added_files(files)

    def apply_preset_crf(self, crf_value):
        """퀵 프로필 버튼 클릭 시 슬라이더 변경 및 마커/추정치 갱신"""
        max_c = self.get_max_crf()
        val = min(max_c, max(18, crf_value))
        self.crf_var.set(val)
        self.on_crf_change(val)
        self.draw_crf_markers()

    def auto_select_hw_accelerator_for_codec(self):
        """[v4.60] 선택한 출력 코덱에 맞춰 GPU 가속 지원 여부를 자동 감지하여 가속 장치 자동 선택"""
        if not hasattr(self, 'combo_codec') or not self.combo_codec or not hasattr(self, 'combo_hw') or not self.combo_hw:
            return

        codec_str = self.combo_codec.get()
        if "VP9" in codec_str or "MP3" in codec_str:
            self.combo_hw.current(3)  # CPU 전용
            return

        vendor = self.detected_gpu_vendor
        target_hw_encoder = None

        if "AV1" in codec_str:
            if vendor == "NVIDIA":
                target_hw_encoder = "av1_nvenc"
            elif vendor == "AMD":
                target_hw_encoder = "av1_amf"
            elif vendor == "Intel":
                target_hw_encoder = "av1_qsv"
        elif "H.265" in codec_str or "MKV" in codec_str:
            if vendor == "NVIDIA":
                target_hw_encoder = "hevc_nvenc"
            elif vendor == "AMD":
                target_hw_encoder = "hevc_amf"
            elif vendor == "Intel":
                target_hw_encoder = "hevc_qsv"
        elif "H.264" in codec_str:
            if vendor == "NVIDIA":
                target_hw_encoder = "h264_nvenc"
            elif vendor == "AMD":
                target_hw_encoder = "h264_amf"
            elif vendor == "Intel":
                target_hw_encoder = "h264_qsv"

        if target_hw_encoder and self.test_encoder_works(target_hw_encoder):
            if vendor == "AMD":
                self.combo_hw.current(0)
            elif vendor == "NVIDIA":
                self.combo_hw.current(1)
            elif vendor == "Intel":
                self.combo_hw.current(2)
        else:
            # 해당 코덱의 HW 가속을 GPU가 지원하지 않는 경우 -> CPU 전용으로 자동 설정
            self.combo_hw.current(3)

    def on_codec_change(self, *args):
        codec = self.combo_codec.get()
        # [v4.54] AV1 선택 시 슬라이더 최대 범위를 63으로 확장, 기타 코덱은 50으로 설정
        max_crf = self.get_max_crf()
        if hasattr(self, 'scale_crf'):
            self.scale_crf.config(to=max_crf)
            if self.crf_var.get() > max_crf:
                self.crf_var.set(max_crf)

        # [v4.60] 선택 코덱에 맞춰 가속 장치 자동 선택
        self.auto_select_hw_accelerator_for_codec()

        if "MP3" in codec:
            self.combo_format.config(state="readonly")
            vals = list(self.combo_format['values'])
            if "MP3 (.mp3)" in vals:
                self.combo_format.current(vals.index("MP3 (.mp3)"))
            self.combo_format.config(state="disabled")
            self.combo_res.config(state="disabled")
            self.combo_fps.config(state="disabled")
        elif "MKV" in codec:
            self.combo_format.config(state="readonly")
            self.combo_format.current(1)  # MKV (.mkv)
            self.combo_format.config(state="disabled")
            self.combo_res.config(state="normal")
            self.combo_fps.config(state="readonly")
            self.ensure_codec_or_offer_install("libx265", "H.265 (MKV 방식 내부 코덱)")
        else:
            self.combo_format.config(state="readonly")
            self.combo_res.config(state="normal")
            self.combo_fps.config(state="readonly")
            # 필요 인코더 사전 확인
            if "AV1" in codec:
                self.ensure_codec_or_offer_install("libsvtav1", "AV1")
            elif "VP9" in codec:
                self.ensure_codec_or_offer_install("libvpx-vp9", "VP9")

        self.refresh_preset_chips()
        self.sync_controls_to_selected_items('codec', codec)
        self.auto_apply_recommended_crf()
        self.draw_crf_markers()

    def on_format_change(self, *args):
        """[v4.60] AV1/VP9 코덱 상태에서 사용자가 출력 포맷을 MP4로 변경하려 할 때 안내 팝업 표시"""
        codec = self.combo_codec.get() if hasattr(self, 'combo_codec') and self.combo_codec else ""
        fmt = self.combo_format.get() if hasattr(self, 'combo_format') and self.combo_format else ""

        if ("AV1" in codec or "VP9" in codec) and "MP4" in fmt:
            codec_name = codec.split(' ')[0]
            msg = (
                f"💡 [{codec_name} 코덱 출력 포맷 변경 안내]\n\n"
                f"선택하신 {codec_name} 코덱은 MKV 포맷 사용이 권장됩니다.\n\n"
                "📌 [포맷별 특징 비교]\n"
                "• MP4 선택 (예)   : PC·스마트폰·웹 브라우저·유튜브 공유용으로 완벽히 정상 동작합니다.\n"
                "• MKV 유지 (아니오): 구형 스마트 TV 재생 및 다국어 자막/오디오 트랙 보존에 최적화되어 추천됩니다.\n\n"
                "출력 포맷을 MP4(.mp4)로 변경하시겠습니까?\n"
                "(아니오 선택 시 권장 포맷인 MKV(.mkv)가 유지됩니다.)"
            )
            if not messagebox.askyesno("출력 포맷 변경 안내", msg, parent=self.root):
                self.combo_format.current(1)  # MKV (.mkv)로 원상 복귀
        self.update_estimations()

    def on_crf_change(self, val):
        v = self.crf_var.get()
        combo_val = getattr(self, 'combo_codec', None).get() if getattr(self, 'combo_codec', None) else ""
        is_av1 = "AV1" in combo_val

        if is_av1:
            if v <= 26:
                desc = "💎 원본급 최고화질 (용량 ~50% 절감)"
                color = "#15803d"
            elif v <= 33:
                desc = "⭐ 동일화질 균형추천 (용량 ~65% 절감)"
                color = "#166534"
            elif v <= 41:
                desc = "🚀 고강도 용량절약 (용량 ~80% 절감 · 추천)"
                color = "#b45309"
            elif v <= 52:
                desc = "📦 극강 초고압축 (용량 ~88% 절감 · 보관용)"
                color = "#c2410c"
            elif v <= 58:
                desc = "⚡ 컴팩트 초경량 보관 (용량 ~93% 절감)"
                color = "#991b1b"
            else:
                desc = "🔥 규격 한계값 극한경량 (용량 ~96%+ 절감)"
                color = "#7f1d1d"
        else:
            if v <= 22:
                desc = "고화질 (용량 커짐)"
                color = "#15803d"
            elif v <= 27:
                desc = "표준 화질 (균형)"
                color = "#166534"
            elif v <= 34:
                desc = "용량 절약 (화질 저하 주의)"
                color = "#b45309"
            else:
                desc = "고압축·저화질"
                color = "#c2410c"

        self.lbl_crf_val.config(text=f"{v:>2} · {desc}", fg=color)
        self.sync_controls_to_selected_items('crf', v)
        self.update_estimations()

    # ==================================================================
    #  파일 목록 / 예측
    # ==================================================================
    #  [v4.61] 다양한 구형/신형 동영상 포맷 전체 지원 (.3gp, .wmv, .avi, .mov, .flv, .mpg, .vob, .ts 등)
    # ==================================================================
    #  [v4.61] 다양한 구형/신형 동영상 및 Motion JPEG 포맷 전체 지원 (.jpg, .jpeg, .jpe, .mjpg, .mjpeg 등)
    # ==================================================================
    VIDEO_EXTS = (
        '.mp4', '.mkv', '.avi', '.mov', '.webm', '.wmv',
        '.3gp', '.3g2', '.flv', '.f4v', '.asf', '.divx',
        '.mpg', '.mpeg', '.m2v', '.vob', '.ts', '.mts',
        '.m2ts', '.tp', '.m4v', '.ogv', '.qt',
        '.jpe', '.jpeg', '.jpg', '.mjpg', '.mjpeg', '.mjp'
    )

    @staticmethod
    def _natural_sort_key(path_str):
        """파일명 기준 가나다/자연어(숫자 인식) 정렬 키"""
        name = os.path.basename(path_str)
        return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', name)]

    def handle_drop(self, event):
        entries = self.root.tk.splitlist(event.data)
        all_files = []
        for e in entries:
            p = Path(e)
            if p.is_dir():
                found = self.scan_folder_for_videos(p)
                if found:
                    all_files.extend(found)
            elif p.is_file() and p.suffix.lower() in self.VIDEO_EXTS:
                if '_압축본_' not in p.name:
                    all_files.append(str(p))
        if all_files:
            self.process_added_files(all_files)

    def format_size(self, size_bytes):
        if size_bytes >= 1024**3:
            return f"{size_bytes / (1024**3):.2f} GB"
        else:
            return f"{size_bytes / (1024**2):.1f} MB"

    def format_time(self, seconds):
        seconds = int(seconds)
        if seconds > 3600:
            return f"{seconds//3600}시간 {(seconds%3600)//60}분"
        elif seconds > 60:
            return f"{seconds//60}분 {seconds%60}초"
        else:
            return f"{seconds}초"

    @staticmethod
    def win32_askopenfilenames(title="비디오 및 사진 파일 선택", initialdir=None, parent_hwnd=None):
        """[v4.631L] Win32 API GetOpenFileNameW를 직접 호출하여
        드롭다운 필터 라벨에 불필요한 확장자 목록((*.mp4;*.mkv...))이 자동 덧붙지 않도록
        100% 깔끔한 서식의 네이티브 대화상자를 띄운다."""
        if os.name != 'nt':
            return None

        try:
            import ctypes
            from ctypes import wintypes

            class OPENFILENAMEW(ctypes.Structure):
                _fields_ = [
                    ('lStructSize', wintypes.DWORD), ('hwndOwner', wintypes.HWND),
                    ('hInstance', wintypes.HINSTANCE), ('lpstrFilter', wintypes.LPCWSTR),
                    ('lpstrCustomFilter', wintypes.LPWSTR), ('nMaxCustFilter', wintypes.DWORD),
                    ('nFilterIndex', wintypes.DWORD), ('lpstrFile', wintypes.LPWSTR),
                    ('nMaxFile', wintypes.DWORD), ('lpstrFileTitle', wintypes.LPWSTR),
                    ('nMaxFileTitle', wintypes.DWORD), ('lpstrInitialDir', wintypes.LPCWSTR),
                    ('lpstrTitle', wintypes.LPCWSTR), ('Flags', wintypes.DWORD),
                    ('nFileOffset', wintypes.WORD), ('nFileExtension', wintypes.WORD),
                    ('lpstrDefExt', wintypes.LPCWSTR), ('lCustData', wintypes.LPARAM),
                    ('lpfnHook', wintypes.LPARAM), ('lpTemplateName', wintypes.LPCWSTR),
                    ('pvReserved', wintypes.LPVOID), ('dwReserved', wintypes.DWORD),
                    ('FlagsEx', wintypes.DWORD),
                ]

            filter_parts = [
                "🎬 모든 비디오 및 사진 지원 포맷\0*.mp4;*.mkv;*.avi;*.mov;*.webm;*.wmv;*.3gp;*.3g2;*.flv;*.f4v;*.asf;*.divx;*.mpg;*.mpeg;*.m2v;*.vob;*.ts;*.mts;*.m2ts;*.tp;*.m4v;*.ogv;*.qt;*.jpg;*.jpeg;*.jpe;*.mjpg;*.mjpeg;*.mjp",
                "🖼️ 정지 사진 (JPG/JPEG)\0*.jpg;*.jpeg;*.jpe",
                "📹 모션 JPEG (영상+음성)\0*.jpg;*.jpeg;*.jpe;*.mjpg;*.mjpeg;*.mjp",
                "🎥 동영상 파일\0*.mp4;*.mkv;*.avi;*.mov;*.webm;*.wmv;*.3gp;*.3g2;*.flv;*.f4v;*.asf;*.divx;*.mpg;*.mpeg;*.m2v;*.vob;*.ts;*.mts;*.m2ts;*.tp;*.m4v;*.ogv;*.qt",
                "📄 모든 파일 (*.*)\0*.*"
            ]
            filter_str = "\0".join(filter_parts) + "\0\0"

            buffer_size = 65536
            file_buffer = ctypes.create_unicode_buffer(buffer_size)
            dir_str = str(initialdir) if initialdir else os.getcwd()

            ofn = OPENFILENAMEW()
            ofn.lStructSize = ctypes.sizeof(OPENFILENAMEW)
            ofn.hwndOwner = parent_hwnd or 0
            ofn.lpstrFilter = filter_str
            ofn.lpstrFile = ctypes.cast(file_buffer, wintypes.LPWSTR)
            ofn.nMaxFile = buffer_size
            ofn.lpstrInitialDir = dir_str
            ofn.lpstrTitle = title
            # OFN_EXPLORER(0x80000) | OFN_ALLOWMULTISELECT(0x200) | OFN_FILEMUSTEXIST(0x1000) | OFN_PATHMUSTEXIST(0x800)
            ofn.Flags = 0x00080000 | 0x00000200 | 0x00001000 | 0x00000800
            ofn.nFilterIndex = 4  # [v4.65t] 기본 선택 필터: 4번째 항목 '🎥 동영상 파일'

            if ctypes.windll.comdlg32.GetOpenFileNameW(ctypes.byref(ofn)):
                buf_str = file_buffer[:]
                null_pos = buf_str.find('\x00\x00')
                if null_pos != -1:
                    buf_str = buf_str[:null_pos]
                parts = [p for p in buf_str.split('\x00') if p]
                if not parts:
                    return []
                if len(parts) == 1:
                    return [parts[0]]
                else:
                    dir_path = parts[0]
                    return [os.path.join(dir_path, fname) for fname in parts[1:]]
            else:
                return []
        except Exception as e:
            print(f"Win32 GetOpenFileNameW 예외 발생: {e}")
        return []

    def add_files(self):
        WidgetToolTip.hide_all_tips()  # [v4.631M] 툴팁 팝업 즉시 닫기
        hwnd = None
        try:
            hwnd = self.root.winfo_id()
        except Exception:
            hwnd = None

        if os.name == 'nt':
            files = self.win32_askopenfilenames(title="비디오 및 사진 파일 선택", parent_hwnd=hwnd)
        else:
            all_pattern = " ".join(f"*{ext}" for ext in self.VIDEO_EXTS)
            video_pattern = " ".join(f"*{ext}" for ext in self.VIDEO_EXTS if ext not in ('.jpg', '.jpeg', '.jpe'))
            photo_pattern = "*.jpg *.jpeg *.jpe"
            mjpeg_pattern = "*.jpg *.jpeg *.jpe *.mjpg *.mjpeg *.mjp"

            files = filedialog.askopenfilenames(
                title="비디오 및 사진 파일 선택",
                filetypes=[
                    ("🎥 동영상 파일 (동영상만)", video_pattern),
                    ("🎬 모든 비디오 및 사진 지원 포맷 (전체)", all_pattern),
                    ("🖼️ 정지 사진 (JPG/JPEG)", photo_pattern),
                    ("📹 모션 JPEG (영상+음성)", mjpeg_pattern),
                    ("📄 모든 파일 (*.*)", "*.*")
                ]
            )

        if files:
            self.process_added_files(files)

    # ==================================================================
    #  [v3.0] 폴더 및 하위 폴더 일괄 추가
    # ==================================================================
    def scan_folder_for_videos(self, folder, include_subfolders=True):
        """폴더에서 비디오 파일을 탐색 (include_subfolders=True 시 하위 폴더 재귀 탐색).
        이 프로그램이 만든 기존/신규 결과물은 재압축을 막기 위해 제외한다."""
        found = []
        generated_name_re = re.compile(
            r'_(?:MKV_HEVC|HEVC|AV1|VP9|H264)_(?:\d+x\d+|1080p|720p|480p)_CRF\d+(?: \(\d+\))?$',
            re.IGNORECASE)
        try:
            folder_path = Path(folder).resolve()
            search_glob = folder_path.rglob('*') if include_subfolders else folder_path.glob('*')
            for p in sorted(search_glob):
                try:
                    if not p.is_file():
                        continue
                    if p.suffix.lower() not in self.VIDEO_EXTS:
                        continue
                    # 예전 '_압축본_' 이름과 v3.1 이후의 '코덱_해상도_CRF' 이름을 모두 제외
                    if '_압축본_' in p.name or generated_name_re.search(p.stem):
                        continue
                    # 지정 저장 폴더가 스캔 대상 안에 있으면 출력물 재수집 방지
                    if self.output_dir:
                        try:
                            p.resolve().relative_to(Path(self.output_dir).resolve())
                            continue
                        except ValueError:
                            pass
                    found.append(str(p.resolve()))
                except OSError:
                    continue
        except Exception as e:
            print(f"폴더 스캔 오류: {e}")
        found.sort(key=self._natural_sort_key)
        return found

    def add_folder(self):
        WidgetToolTip.hide_all_tips()  # [v4.631M] 툴팁 팝업 즉시 닫기
        folder = filedialog.askdirectory(title="압축할 동영상이 들어있는 폴더 선택")
        if not folder:
            return

        # [v4.67f] 하위 폴더 포함 탐색 여부 사용자가 직접 선택
        include_subfolders = messagebox.askyesno(
            "폴더 탐색 범위 선택",
            f"선택한 폴더:\n{folder}\n\n"
            "하위 폴더까지 모두 포함하여 동영상을 찾을까요?\n\n"
            "• [예]: 하위 폴더 전체 재귀 탐색\n"
            "• [아니오]: 선택한 폴더 안의 파일만 탐색",
            parent=self.root)

        found = self.scan_folder_for_videos(folder, include_subfolders=include_subfolders)
        if not found:
            sub_msg = "(하위 폴더 포함)" if include_subfolders else "(선택 폴더 내부만)"
            messagebox.showinfo("안내", f"선택한 폴더{sub_msg}에서 동영상 파일을 찾지 못했습니다.", parent=self.root)
            return
        if len(found) > 200:
            if not messagebox.askyesno("확인", f"동영상 {len(found)}개가 발견되었습니다.\n모두 대기열에 추가할까요?", parent=self.root):
                return
        self.process_added_files(found, src_root=folder)
        # 폴더 일괄 작업 시 저장 폴더 미지정이면 지정 여부를 안내
        if self.output_mode.get() != 'custom':
            if messagebox.askyesno("저장 위치",
                                   f"동영상 {len(found)}개를 대기열에 추가합니다.\n\n"
                                   "결과물을 별도의 '지정 폴더'에 원본 하위 폴더 구조 그대로 저장할까요?\n"
                                   "(아니오 선택 시 각 원본 파일과 같은 폴더에 저장)", parent=self.root):
                self.choose_output_dir()

    def check_is_running(self):
        """[v4.55] 실제 동작 중인 FFmpeg 프로세스가 없으면 is_running 상태를 안전하게 자동 해제"""
        if self.current_process is None or (hasattr(self.current_process, 'poll') and self.current_process.poll() is not None):
            self.is_running = False
        return self.is_running

    def clear_all(self):
        """[v4.644] 전체 대기열 목록을 비우고 모든 인코딩 상세 설정(코덱, 가속장치, CRF 화질, 해상도, FPS, 저장 경로, 병합 및 자막 옵션)을 기본값으로 완전 초기화"""
        if self.check_is_running():
            messagebox.showwarning("안내", "작업이 진행 중일 때는 목록을 비울 수 없습니다.", parent=self.root)
            return
        if self.file_list and not messagebox.askyesno("확인", "전체 목록을 비우고 인코딩 상세 설정을 모두 초기화하시겠습니까?", parent=self.root):
            return

        # 1. 트리뷰 및 파일 목록 비우기
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.file_list = []
        self._batch_used_outputs = set()

        # 2. 인코딩 주요 옵션 (가속장치 / 코덱 / 포맷 / 해상도 / FPS / 오디오) 기본값 초기화
        if hasattr(self, 'combo_codec') and self.combo_codec:
            self.combo_codec.current(0)  # AV1
        if hasattr(self, 'combo_format') and self.combo_format:
            self.combo_format.current(1)  # MKV (.mkv)
        if hasattr(self, 'combo_res') and self.combo_res:
            self.combo_res.current(0)  # 원본 유지
        if hasattr(self, 'combo_fps') and self.combo_fps:
            self.combo_fps.current(0)  # 원본 유지
        if hasattr(self, 'combo_audio') and self.combo_audio:
            self.combo_audio.current(0)  # 원본 유지

        # 가속 장치 기본값 (GPU 지원 여부에 맞게 자동 감지 초기화)
        if hasattr(self, 'auto_select_hw_accelerator_for_codec'):
            self.auto_select_hw_accelerator_for_codec()
        elif hasattr(self, 'combo_hw') and self.combo_hw:
            if getattr(self, 'detected_gpu_vendor', '') == "NVIDIA":
                self.combo_hw.current(1)
            elif getattr(self, 'detected_gpu_vendor', '') == "Intel":
                self.combo_hw.current(2)
            elif getattr(self, 'detected_gpu_vendor', '') == "AMD":
                self.combo_hw.current(0)
            else:
                self.combo_hw.current(3)

        # 3. 화질 (CRF 슬라이더) 초기화 (기본값: 25)
        if hasattr(self, 'crf_var'):
            self.crf_var.set(25)
            if hasattr(self, 'on_crf_change'):
                self.on_crf_change(25)
            if hasattr(self, 'draw_crf_markers'):
                self.draw_crf_markers()

        # 4. 저장 위치 및 파일명 옵션 초기화
        if hasattr(self, 'output_mode'):
            self.output_mode.set('source')
        self.output_dir = ""
        if hasattr(self, 'combo_output_mode') and self.combo_output_mode:
            self.combo_output_mode.current(0)
        if hasattr(self, '_refresh_outdir_widgets'):
            self._refresh_outdir_widgets()

        if hasattr(self, 'filename_mode_var'):
            self.filename_mode_var.set("새로운 파일명 사용(기존명칭+인코딩 정보)")
        if hasattr(self, 'keep_orig_name'):
            self.keep_orig_name.set(False)
        if hasattr(self, 'delete_orig_file'):
            self.delete_orig_file.set(False)
        if hasattr(self, 'skip_info_file'):
            self.skip_info_file.set(False)
        if hasattr(self, 'skip_duplicate_files'):
            self.skip_duplicate_files.set(False)
        if hasattr(self, 'photo_option_var'):
            self.photo_option_var.set("모션 JPEG만 작업(음성 포함)")
        if hasattr(self, 'combo_photo_option') and self.combo_photo_option:
            self.combo_photo_option.current(0)

        # 5. 병합 및 자막 옵션 초기화
        if hasattr(self, 'merge_mode'):
            self.merge_mode.set(False)
        if hasattr(self, 'combo_merge_fit') and self.combo_merge_fit:
            self.combo_merge_fit.current(1)
        if hasattr(self, 'on_merge_mode_toggle'):
            self.on_merge_mode_toggle()

        if hasattr(self, 'merge_caption_mode'):
            self.merge_caption_mode.set(False)
        if hasattr(self, 'caption_duration_var'):
            self.caption_duration_var.set("계속")
        if hasattr(self, 'caption_custom_sec'):
            self.caption_custom_sec.set("5")
        if hasattr(self, 'caption_theme_var'):
            self.caption_theme_var.set("🌈 레인보우 네온 (기본값)")
        if hasattr(self, '_on_caption_mode_toggle'):
            self._on_caption_mode_toggle()

        # 6. 자동 화질 및 상태 초기화
        if hasattr(self, 'auto_quality_profile_var'):
            self.auto_quality_profile_var.set("")
        self.crf_global_apply_confirmed = False
        self.precise_quality_running = False
        self.precise_quality_generation += 1
        if hasattr(self, '_refresh_auto_quality_profile_options'):
            self._refresh_auto_quality_profile_options()
        if hasattr(self, '_set_auto_quality_status'):
            self._set_auto_quality_status("자동화질 준비", "#6b7280")

        # 7. 하단 통계/프레임 및 퀵 프로필 갱신
        if hasattr(self, 'refresh_preset_chips'):
            self.refresh_preset_chips()
        self.lbl_stats.config(text="대기 중입니다.")
        self.progress['value'] = 0
        self.btn_start.config(state="normal")
        self.btn_cancel.config(state="disabled")
        self.update_estimations()

    def reset_completed_items(self):
        """[v4.60 UX] 변환 완료된 대기열 항목들을 다시 대기 상태로 되돌려 재압축/재작업이 가능하도록 초기화"""
        if self.check_is_running():
            messagebox.showwarning("안내", "작업이 진행 중일 때는 항목을 초기화할 수 없습니다.", parent=self.root)
            return

        reset_count = 0
        for item in self.file_list:
            status_str = str(item.get('status', ''))
            if "완료" in status_str:
                item['status'] = "대기 중"
                item['out_path'] = None
                item['used_crf'] = None
                item['checked'] = True

                item_id = item['id']
                self.tree.item(item_id, tags=())
                self.tree.set(item_id, "chk", "☑")
                self.tree.set(item_id, "result_codec", "-")
                self.tree.set(item_id, "size_info", "-")
                self.tree.set(item_id, "ratio_info", "-")
                self.tree.set(item_id, "status", "대기 중")
                reset_count += 1

        if reset_count > 0:
            self.update_summary()
            self.update_estimations()
            messagebox.showinfo(
                "🔄 완료 항목 재작업 준비 완료",
                f"총 {reset_count}개의 완료된 비디오 항목이 '대기 중'으로 초기화되었습니다.\n\n"
                "원하시는 인코딩 옵션을 설정하신 후 '▶ 작업 시작'을 누르시면 재작업이 진행됩니다.", parent=self.root)
        else:
            messagebox.showinfo("안내", "대기열 목록에 완료된 항목이 없습니다.", parent=self.root)


    # ==================================================================
    #  [v2.4] 화질(CRF) 예측 모델
    #   - 크기 모델: CRF +6 마다 용량 절반 (x264/x265/AV1 공통 경험칙)
    #   - 코덱 효율(동일 화질 시 H.264 대비 크기 비율)로 원본/출력 코덱을 환산
    # ==================================================================
    CODEC_EFFICIENCY = {
        'AV1': 0.55, 'HEVC': 0.68, 'H265': 0.68, 'VP9': 0.76,
        'H264': 1.0, 'AVC': 1.0,
        'MPEG4': 1.6, 'MSMPEG4V3': 1.6, 'WMV3': 1.5, 'WMV2': 1.7,
        'VC1': 1.3, 'MPEG2VIDEO': 2.0, 'MPEG1VIDEO': 2.5,
    }

    AUTO_QUALITY_PROFILES = (
        "동일 용량",
        "동일 화질",
        "절약 추천",
        "현재값 -3 (화질▲·용량▲)",
        "현재값 -2 (화질▲·용량▲)",
        "현재값 -1 (화질▲·용량▲)",
        "현재값 +1 (화질▼·용량▼)",
        "현재값 +2 (화질▼·용량▼)",
        "현재값 +3 (화질▼·용량▼)",
    )
    PRECISE_OFFSET_PROFILES = (
        "정밀추천 대비 CRF -3 (화질 향상▲·용량 증가▲)",
        "정밀추천 대비 CRF -2 (화질 향상▲·용량 증가▲)",
        "정밀추천 대비 CRF -1 (화질 향상▲·용량 증가▲)",
        "정밀추천 대비 CRF +1 (화질 저하▼·용량 감소▼)",
        "정밀추천 대비 CRF +2 (화질 저하▼·용량 감소▼)",
        "정밀추천 대비 CRF +3 (화질 저하▼·용량 감소▼)",
    )
    VMAF_TARGET = 94.0
    SSIM_TARGET = 0.970
    PSNR_TARGET = 40.0
    AUTO_SIZE_TARGET_RATIO = 0.88

    def get_src_codec_weight(self, codec_name):
        key = re.sub(r'[^A-Z0-9]', '', str(codec_name).upper())
        return self.CODEC_EFFICIENCY.get(key, 1.0)

    def get_out_codec_weight(self, codec_choice=None):
        """예상 용량 과소평가를 줄인 보수적 출력 코덱 효율값."""
        codec = codec_choice or self.combo_codec.get()
        if "AV1" in codec:
            return 0.55
        if "H.265" in codec or "MKV" in codec:
            return 0.68
        if "VP9" in codec:
            return 0.76
        return 1.0

    def get_prediction_safety_factor(self):
        """CRF 인코더·영상 복잡도 편차를 예상 크기에 반영하는 안전계수."""
        try:
            hw = self.combo_hw.get()
        except Exception:
            hw = "CPU"
        return 1.45 if "CPU" in hw else 1.70

    def get_auto_crf_floor(self):
        """고비트레이트 원본에서 지나치게 낮은 CRF가 선택되는 것을 막는 안전 하한."""
        try:
            codec = self.combo_codec.get()
            hw = self.combo_hw.get()
        except Exception:
            codec, hw = "H.265", "CPU"
        if "AV1" in codec:
            floor = 32
        elif "VP9" in codec:
            floor = 25
        elif "H.265" in codec or "MKV" in codec:
            floor = 23
        else:
            floor = 21
        if "CPU" not in hw:
            floor += 1
        return floor

    def get_audio_bps(self, item=None):
        if self.audio_copy_selected():
            src = (item or {}).get('audio_bps_src', 0)
            return src if src > 0 else 128000
        try:
            return int(self.get_audio_encode_bitrate().rstrip('k')) * 1000
        except Exception:
            return 128000

    @staticmethod
    def parse_resolution_setting(res_choice, orig_w=None, orig_h=None):
        """[v4.60] 해상도 설정 분석 (드롭다운 선택 및 사용자 직접 입력 수용).

        반환값: (tw, th, vf_scale_filter, res_label)
        - 원본 유지 / 입력 없음: (None, None, None, "원본 유지")
        - WxH 직접 입력 (예: 1280x720, 1920x1080, 1024*768): (1280, 720, "scale=1280:720", "1280x720")
        - 높이만 입력 (예: 720p, 1080, 480): (계산된W, 720, "scale=-2:720", "720p")
        """
        if not res_choice or not isinstance(res_choice, str):
            return None, None, None, "원본 유지"

        s = res_choice.strip()
        if not s or "원본" in s or "유지" in s or "직접" in s or "사용자" in s:
            return None, None, None, "원본 유지"

        # 1. WxH 패턴 검사 (예: 3840x2160 (UHD), 1920x1080, 1280*720, 1024 x 768)
        m_wxh = re.search(r'(\d{3,5})\s*[*xX,/]\s*(\d{3,5})', s)
        if m_wxh:
            tw = int(m_wxh.group(1))
            th = int(m_wxh.group(2))
            tw = tw if tw % 2 == 0 else tw - 1
            th = th if th % 2 == 0 else th - 1
            return tw, th, f"scale={tw}:{th}", f"{tw}x{th}"

        # 2. 높이/숫자만 입력된 경우 (예: 720p, 1080, 480, 1440)
        m_h = re.search(r'(\d{3,5})', s)
        if m_h:
            th = int(m_h.group(1))
            th = th if th % 2 == 0 else th - 1
            tw = None
            if orig_w and orig_h and orig_h > 0:
                tw = int(orig_w * (th / orig_h))
                tw = tw if tw % 2 == 0 else tw - 1
            return tw, th, f"scale=-2:{th}", f"{th}p"

        return None, None, None, "원본 유지"

    def estimate_file_params(self, item):
        """파일별 보수적 화질 기준점과 예상 비트레이트를 계산한다.

        기존 코덱 효율 경험식에 인코더 안전계수를 적용하고, 자동 추천 CRF의
        보수적 예상 결과가 원본의 88%를 넘지 않도록 크기 가드 CRF를 사용한다.
        """
        dur = item.get('duration', 0)
        size_b = item.get('orig_size_b', 0)
        if dur <= 0 or size_b <= 0:
            return None

        audio_bps = self.get_audio_bps(item)
        v_bps = item.get('orig_bitrate_b', 0)
        if v_bps <= 0:
            v_bps = max(50000, size_b * 8 / dur - audio_bps)

        w = item.get('orig_width') or 1920
        h = item.get('orig_height') or 1080
        fps = item.get('orig_fps') or 30.0
        pixels = max(1, int(w) * int(h))

        b_eq = v_bps / self.get_src_codec_weight(item.get('orig_codec', ''))
        ref_bps = 4500000 * (pixels / (1920 * 1080)) * (min(fps, 120) / 30.0) ** 0.75
        ref_bps = max(ref_bps, 100000)

        # [v4.65q FIX] 출력 코덱별 CRF 민감도(crf_divisor) 동적 할당으로 예상 크기 정확도 대폭 개선
        out_codec = getattr(self, 'combo_codec', None).get() if getattr(self, 'combo_codec', None) else ""
        if "AV1" in out_codec:
            crf_codec_offset = 8
            crf_divisor = 10.0  # AV1은 H264 대비 CRF 곡선이 매우 완만하여 용량이 덜 줄어듦
        elif "VP9" in out_codec:
            crf_codec_offset = 6
            crf_divisor = 7.5
        else:
            crf_codec_offset = 0
            crf_divisor = 6.0

        crf_anchor = (23 + crf_codec_offset) - crf_divisor * math.log2(max(b_eq, 1) / ref_bps)

        res_choice = self.combo_res.get()
        _, th, _, _ = self.parse_resolution_setting(res_choice)
        target_h = th
        res_factor = 1.0
        if target_h and h and target_h < h:
            res_factor = (target_h / h) ** 1.5

        base_video_bps = (b_eq * self.get_out_codec_weight() * res_factor
                          * self.get_prediction_safety_factor())

        # 원본보다 커지는 결과를 피하기 위한 보수적 목표: 원본 총 크기의 88%.
        target_total_bps = size_b * 8 / dur * self.AUTO_SIZE_TARGET_RATIO
        target_video_bps = max(50000, target_total_bps - audio_bps)
        crf_size_guard = crf_anchor
        if base_video_bps > 0 and target_video_bps > 0:
            crf_size_guard = crf_anchor + crf_divisor * math.log2(base_video_bps / target_video_bps)
        recommended_crf = max(crf_anchor, crf_size_guard, self.get_auto_crf_floor())

        target_same_size_v_bps = size_b * 8 / dur - audio_bps
        crf_same_size = None
        if target_same_size_v_bps > 0 and base_video_bps > 0:
            crf_same_size = crf_anchor + crf_divisor * math.log2(base_video_bps / target_same_size_v_bps)

        return {
            'crf_same_quality': recommended_crf,
            'crf_quality_anchor': crf_anchor,
            'crf_same_size': crf_same_size,
            'base_video_bps': base_video_bps,
            'audio_bps': audio_bps,
            'safety_factor': self.get_prediction_safety_factor(),
            'crf_divisor': crf_divisor,
        }

    def estimate_size_at_crf(self, item, crf):
        """안전계수가 반영된 지정 CRF 예상 결과 크기(바이트)."""
        p = self.estimate_file_params(item)
        if not p:
            return item.get('orig_size_b', 0)
        anchor = p.get('crf_quality_anchor', p['crf_same_quality'])
        divisor = p.get('crf_divisor', 6.0)
        v_bps = p['base_video_bps'] * 2 ** ((anchor - crf) / divisor)
        return (v_bps + p['audio_bps']) * item['duration'] / 8 * 1.02

    def estimate_item_size_and_time(self, item, eff_crf):
        """[v4.52] 지정된 CRF에서의 예상 결과 크기(바이트)와 예상 소요 시간(초)을 계산한다."""
        est_bytes = self.estimate_size_at_crf(item, eff_crf)
        duration = item.get('duration', 0.0)
        hw = getattr(self, 'combo_hw', None)
        hw_str = hw.get() if hw else ""
        if "CPU" in hw_str:
            speed_ratio = 1.2
        elif "NVIDIA" in hw_str or "NVENC" in hw_str:
            speed_ratio = 5.0
        elif "AMD" in hw_str or "AMF" in hw_str:
            speed_ratio = 4.5
        elif "Intel" in hw_str or "QSV" in hw_str:
            speed_ratio = 4.5
        else:
            speed_ratio = 3.0
        est_time = max(1.0, duration / speed_ratio) if duration > 0 else 5.0
        return est_bytes, est_time

    def get_effective_crf(self, item, gui_snapshot=None):
        """[v4.65u] 파일별 자동화질 프로필·정밀 분석값·수동값을 반영한 CRF (백그라운드 스레드 안전)."""
        max_c = self.get_max_crf()
        mode = item.get('crf_mode', 'auto_q') # 기본값 변경: global에서 auto_q로
        p = self.estimate_file_params(item)
        crf_fallback = gui_snapshot.get('crf', 28) if gui_snapshot else (self.crf_var.get() if hasattr(self, 'crf_var') else 28)
        
        raw_same_q = round(p['crf_same_quality']) if p else crf_fallback
        raw_same_s = round(p['crf_same_size']) if (p and p.get('crf_same_size') is not None) else crf_fallback + 2
        
        base_same_q = max(18, min(max_c, raw_same_q))
        base_same_s = max(18, min(max_c, raw_same_s))

        out_codec = getattr(self, 'combo_codec', None).get() if getattr(self, 'combo_codec', None) else ""
        saver_off = 5 if "AV1" in out_codec else 2

        if mode == 'custom':
            return item.get('custom_crf', crf_fallback)
        elif mode == 'auto_same_size':
            return base_same_s
        elif mode == 'auto_q':
            return base_same_q
        elif mode == 'auto_save_space':
            return min(max_c, base_same_q + saver_off)
            
        elif mode == 'precise_same_size':
            return int(item.get('precise_same_size', base_same_s))
        elif mode == 'precise_same_quality':
            return int(item.get('precise_same_quality', base_same_q))
        elif mode == 'precise_save_space':
            return int(item.get('precise_save_space', min(max_c, base_same_q + saver_off)))
            
        # 기존 호환성 모드
        if mode == 'precise_purple':
            return int(item.get('precise_crf', base_same_q))
        if mode == 'precise_blue':
            return int(item.get('precise_same_quality', base_same_q))
        if mode == 'precise_green':
            return int(item.get('precise_same_size', min(max_c, base_same_s + 2)))
        
        if isinstance(mode, str) and mode.startswith('selected_file_'):
            try:
                return max(18, min(max_c, int(mode.rsplit('_', 1)[-1])))
            except ValueError:
                pass
        if mode == 'auto_precise':
            precise = item.get('precise_crf')
            return max(18, min(max_c, int(precise if precise is not None else base_same_q)))
        if isinstance(mode, str) and mode.startswith('auto_precise_off_'):
            off = self._precise_offset_from_mode(mode)
            precise = item.get('precise_crf')
            base_p = int(precise) if precise is not None else base_same_q
            return max(18, min(max_c, base_p + off))
        if isinstance(mode, str) and mode.startswith('auto_plus_'):
            try:
                step = int(mode.rsplit('_', 1)[-1])
            except ValueError:
                step = 0
            return max(18, min(max_c, base_same_q + step))
        if isinstance(mode, int):
            return max(18, min(max_c, mode))
            
        return crf_fallback

    @staticmethod
    def _precise_offset_from_mode(mode):
        """[v3.4] 'auto_precise_off_+2' → 2, 'auto_precise' → 0."""
        if isinstance(mode, str) and mode.startswith('auto_precise_off_'):
            try:
                return max(-3, min(3, int(mode.rsplit('_', 1)[-1])))
            except ValueError:
                return 0
        return 0

    @staticmethod
    def _precise_offset_meaning(off):
        if off < 0:
            return "화질 향상▲·용량 증가▲"
        if off > 0:
            return "화질 저하▼·용량 감소▼"
        return "추천값 그대로"

    def compute_marker_crfs(self):
        """대기 중 파일들의 duration 가중 평균으로 슬라이더 마커 CRF 계산."""
        total_dur = 0.0
        sum_q = 0.0
        sum_s = 0.0
        has_s = False
        sum_p = 0.0
        dur_p = 0.0
        for item in self.file_list:
            if item.get('status') == "완료":
                continue
            p = self.estimate_file_params(item)
            if not p:
                continue
            d = max(item['duration'], 0.1)
            total_dur += d
            
            # [v4.65x] 정밀 샘플링 결과가 있으면 해당 값을 우선적으로 가중 평균에 편입
            if item.get('precise_same_quality') is not None:
                sum_q += float(item['precise_same_quality']) * d
            else:
                sum_q += p['crf_same_quality'] * d
                
            if item.get('precise_same_size') is not None:
                sum_s += float(item['precise_same_size']) * d
                has_s = True
            elif p.get('crf_same_size') is not None:
                sum_s += p['crf_same_size'] * d
                has_s = True
            if item.get('precise_crf') is not None:
                sum_p += float(item['precise_crf']) * d
                dur_p += d
        if total_dur <= 0:
            return None
        return {'same_quality': sum_q / total_dur,
                'same_size': (sum_s / total_dur) if has_s else None,
                'precise_avg': (sum_p / dur_p) if dur_p > 0 else None}

    def _make_5point_quality_reference(self, item, out_path, snapshot):
        """[v4.66] 영상 전체에서 무작위 5곳(각 0.5초)을 추출하여 결합한 표본 생성 (GPU 가속 + CPU 롤백 백업)"""
        duration = max(0.1, float(item.get('duration', 0.1)))
        clip_dur = 0.5
        total_points = 5

        ref_filt = snapshot['reference_filter']
        hw_choice = snapshot.get('combo_hw', '') if snapshot else ''
        hw_vendor = 'AMD' if 'AMD' in hw_choice else ('NVIDIA' if 'NVIDIA' in hw_choice else ('Intel' if 'Intel' in hw_choice else None))

        def build_ref_cmd(use_hw=True):
            if duration <= clip_dur * total_points:
                vf = ref_filt
                hw_input = []
            else:
                seg_len = duration / total_points
                starts = [random.uniform(i * seg_len, max(i * seg_len, (i + 1) * seg_len - clip_dur)) for i in range(total_points)]
                select_parts = [f"between(t,{s:.3f},{s+clip_dur:.3f})" for s in starts]
                select_str = "+".join(select_parts)

                if use_hw and hw_vendor in ('NVIDIA', 'AMD', 'Intel'):
                    if hw_vendor == 'NVIDIA':
                        hw_input = ['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda']
                        vf = f"select='{select_str}',setpts=N/FRAME_RATE/TB,hwdownload,format=nv12,{ref_filt}"
                    elif hw_vendor == 'AMD':
                        hw_input = ['-hwaccel', 'd3d11va', '-hwaccel_output_format', 'd3d11']
                        vf = f"select='{select_str}',setpts=N/FRAME_RATE/TB,hwdownload,format=nv12,{ref_filt}"
                    else:
                        hw_input = ['-hwaccel', 'qsv', '-hwaccel_output_format', 'qsv']
                        vf = f"select='{select_str}',setpts=N/FRAME_RATE/TB,hwdownload,format=nv12,{ref_filt}"
                else:
                    hw_input = []
                    vf = f"select='{select_str}',setpts=N/FRAME_RATE/TB,{ref_filt}"

            cmd = [self.ffmpeg_path, '-hide_banner', '-loglevel', 'error', '-y']
            cmd.extend(hw_input)
            cmd.extend(['-i', item['path'], '-map', '0:v:0', '-an', '-vf', vf, '-c:v', 'ffv1', '-level', '3', out_path])
            return cmd

        # 1차 시도: HW 디코딩 가속 파이프라인
        cmd = build_ref_cmd(use_hw=True)
        rc, _, err = self._run_quality_command(cmd, timeout=300)

        # 2차 시도: 오류 시 자동 CPU 모드로 Fallback
        if rc != 0 or not os.path.exists(out_path):
            if hw_vendor in ('NVIDIA', 'AMD', 'Intel'):
                self.root.after(0, self._set_auto_quality_status, "⚠️ GPU 가속 오류 발생 -> CPU 전용으로 즉시 자동 전환", "#b45309")
                cmd_cpu = build_ref_cmd(use_hw=False)
                rc, _, err = self._run_quality_command(cmd_cpu, timeout=300)

        if rc != 0 or not os.path.exists(out_path):
            raise RuntimeError(f"5지점 결합 표본 생성 실패: {err.strip()[-500:]}")

    def _find_precise_crf(self, item, snapshot, workdir, use_vmaf, progress_text):
        """[v4.67] 5지점 결합 표본 및 스마트 좁은 탐색 범위를 이용한 초고속 화질 측정"""
        ref_path = os.path.join(workdir, 'reference_5points.mkv')
        self._make_5point_quality_reference(item, ref_path, snapshot)
        refs = [ref_path]

        p = self.estimate_file_params(item)
        est = round(p['crf_same_quality']) if (p and p.get('crf_same_quality')) else (self.crf_var.get() if hasattr(self, 'crf_var') else 28)
        low = max(18, est - 4)
        high = min(45, est + 4)
        best_crf = None
        best_metrics = None

        step = 0
        max_steps = 3

        while low <= high and not self.precise_quality_cancel:
            step += 1
            pct = min(99, int((step / max_steps) * 100))
            item['precise_sampling_progress'] = pct
            self.root.after(0, self.update_estimations)

            mid = (low + high) // 2
            passed, metrics = self._evaluate_quality_crf(
                refs, mid, snapshot, workdir, use_vmaf, progress_text)
            if passed:
                best_crf, best_metrics = mid, metrics
                low = mid + 1
            else:
                high = mid - 1

        if best_crf is None:
            best_crf = max(18, min(45, est))
        return best_crf, best_metrics

    def _run_precise_quality_analysis(self, pending, snapshot, generation):
        use_vmaf = self._supports_libvmaf()
        failures = 0
        temp_root = tempfile.mkdtemp(prefix='svc_quality_')
        try:
            total = len(pending)
            start_time = time.time()
            completed_count = 0

            max_workers = max(2, min(12, (os.cpu_count() or 8)))

            def process_item(index, item_tuple):
                nonlocal completed_count, failures
                if self.precise_quality_cancel or generation != self.precise_quality_generation:
                    return

                item, cache_key = item_tuple
                number = index + 1
                safe_name = os.path.basename(item.get('name', 'video'))[:18]

                completed_count += 1
                pct = int((completed_count / total) * 100)
                elapsed = time.time() - start_time
                if completed_count > 0 and elapsed > 0:
                    avg_per = elapsed / completed_count
                    rem_sec = max(0, int(round(avg_per * (total - completed_count))))
                    eta_str = f"약 {self.format_time(rem_sec)}"
                else:
                    eta_str = "계산 중..."

                progress = f"▶ 정밀 계산 {pct}% ({completed_count}/{total} · 남음: {eta_str}) [{safe_name}]"
                self.root.after(0, self._set_auto_quality_status, progress, "#b45309")

                item['precise_sampling_active'] = True
                item['precise_sampling_progress'] = 0
                self.root.after(0, self.update_estimations)

                item_dir = os.path.join(temp_root, f'item_{number}')
                os.makedirs(item_dir, exist_ok=True)
                try:
                    crf, metrics = self._find_precise_crf(
                        item, snapshot, item_dir, use_vmaf, progress)
                    out_c = getattr(self, 'combo_codec', None).get() if getattr(self, 'combo_codec', None) else ""
                    saver_off = 5 if "AV1" in out_c else 2
                    max_c = self.get_max_crf()
                    int_crf = int(crf)
                    item['precise_crf'] = int_crf
                    item['precise_same_quality'] = int_crf
                    item['precise_same_size'] = min(max_c, int_crf + saver_off)
                    item['precise_save_space'] = min(max_c, int_crf + saver_off)
                    item['precise_metrics'] = metrics or {}
                    item['precise_quality_key'] = cache_key
                except Exception as e:
                    failures += 1
                    item['precise_error'] = str(e)
                finally:
                    item['precise_sampling_active'] = False
                self.root.after(0, self.update_estimations)
                self.root.after(0, self.draw_crf_markers)

            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(process_item, idx, pair) for idx, pair in enumerate(pending)]
                for future in concurrent.futures.as_completed(futures):
                    if self.precise_quality_cancel or generation != self.precise_quality_generation:
                        break
        finally:
            self.precise_quality_running = False
            try:
                import shutil
                shutil.rmtree(temp_root, ignore_errors=True)
            except:
                pass
            if not self.precise_quality_cancel:
                self.root.after(0, lambda: self._set_auto_quality_status("자동화질 반영 완료", "#15803d"))
            self.root.after(0, self.update_estimations)
            self.root.after(0, self.draw_crf_markers)
            btn = getattr(self, 'btn_cancel_precise', None)
            if btn is not None:
                btn.pack_forget()
            combo = getattr(self, 'combo_auto_quality', None)
            if combo is not None:
                combo.config(state="normal")
            self.precise_quality_running = False

    def get_auto_quality_profile(self):
        var = getattr(self, 'auto_quality_profile_var', None)
        if var is not None:
            try:
                return var.get() or "동일화질(보수적)"
            except Exception:
                pass
        return getattr(self, 'auto_quality_profile_value', "동일화질(보수적)")

    def auto_profile_to_mode(self, profile):
        """[v4.65y] 콤보박스 선택값과 체크박스 상태를 조합하여 내부 crf_mode를 결정한다."""
        is_precise = getattr(self, 'precise_sampling_var', None) and self.precise_sampling_var.get()
        if profile == "동일 용량":
            return 'precise_same_size' if is_precise else 'auto_same_size'
        if profile == "절약 추천":
            return 'precise_save_space' if is_precise else 'auto_save_space'
        if profile == "동일 화질":
            return 'precise_same_quality' if is_precise else 'auto_q'
        import re
        m = re.search(r'([+-]\d+)', str(profile))
        if m:
            val = int(m.group(1))
            prefix = "auto_precise_off_" if is_precise else "auto_off_"
            return f"{prefix}{val}"
        return 'precise_same_quality' if is_precise else 'auto_q'


    def _set_auto_quality_status(self, text, color="#6b7280"):
        label = getattr(self, 'lbl_auto_quality_status', None)
        if label is not None:
            try:
                label.config(text=text, fg=color)
            except Exception:
                pass

    def _refresh_auto_quality_profile_options(self):
        """[v4.65u] 옵션이 고정되므로 더 이상 런타임에 동적으로 변경하지 않음."""
        pass


    def on_auto_quality_profile_change(self, *args):
        """[v4.65u] 화질 기준 및 정밀 샘플링 체크박스 변경 시 대기열의 전체 파일에 일괄 적용한다."""
        if getattr(self, 'precise_quality_running', False):
            return
            
        profile = self.get_auto_quality_profile()
        if not profile:
            return
            
        self.auto_quality_profile_value = profile
        target_items = [f for f in getattr(self, 'file_list', []) if f.get('status') != "완료"]
        if not target_items:
            return
            
        mode = self.auto_profile_to_mode(profile)
        is_precise = getattr(self, 'precise_sampling_var', None) and self.precise_sampling_var.get()
        
        for item in target_items:
            item['crf_mode'] = mode
            item.pop('precise_quality_key', None) # 강제 재계산 유도
            
        if is_precise:
            self.start_precise_quality_analysis(target_items)
        else:
            self.update_estimations()


    def prompt_custom_resolution(self):
        """[v4.55] 해상도 드롭다운에서 '사용자 직접 입력...' 선택 시 가로/세로 전용 팝업 창 표시"""
        if getattr(self, '_is_prompting_res', False):
            return
        self._is_prompting_res = True
        try:
            cur = self.combo_res.get()
            tw, th, _, _ = self.parse_resolution_setting(cur)
            prev_w = str(tw) if tw else "1920"
            prev_h = str(th) if th else "1080"

            dlg = CustomResolutionDialog(self.root, prev_w=prev_w, prev_h=prev_h)
            self.root.wait_window(dlg)

            if dlg.result:
                self.combo_res.set(dlg.result)
                self.sync_controls_to_selected_items('res', dlg.result)
            else:
                if cur and ("직접 입력" in cur or "사용자" in cur):
                    self.combo_res.current(0)
                self.sync_controls_to_selected_items('res', self.combo_res.get())
        finally:
            self._is_prompting_res = False
            self.on_quality_setting_change()

    def on_quality_setting_change(self, *args):
        """코덱·가속·해상도·FPS 변경 시 선택 항목에 즉시 반영하고 캐시를 무효화한다."""
        if getattr(self, '_is_prompting_res', False):
            return

        if hasattr(self, 'combo_res'):
            cur_res = self.combo_res.get()
            if cur_res and ("직접 입력" in cur_res or "사용자" in cur_res):
                self.prompt_custom_resolution()
                return
            self.sync_controls_to_selected_items('res', cur_res)
            # 해상도가 변경되었거나 병합 모드 상태에 따라 병합/화면 맞춤 드롭다운 활성화 상태 갱신
            self.update_merge_fit_state()
        if hasattr(self, 'combo_fps'):
            self.sync_controls_to_selected_items('fps', self.combo_fps.get())
        if hasattr(self, 'combo_audio'):
            self.sync_controls_to_selected_items('audio', self.combo_audio.get())

        for item in self.file_list:
            item.pop('precise_quality_key', None)
        if self.get_auto_quality_profile().startswith("정밀"):
            self.start_precise_quality_analysis([
                item for item in self.file_list if item.get('status') != "완료"
            ])
        else:
            self.auto_apply_recommended_crf()

    def auto_apply_recommended_crf(self, *args):
        """현재 자동화질 기준을 새 항목에 반영하고 평균 추천값을 슬라이더에 표시한다."""
        profile = self.get_auto_quality_profile()
        self.auto_quality_profile_value = profile
        mode = self.auto_profile_to_mode(profile)
        for item in self.file_list:
            if item.get('status') != "완료" and item.get('crf_mode') in (None, 'global'):
                item['crf_mode'] = mode
        m = self.compute_marker_crfs()
        if m and m.get('same_quality') is not None:
            value = round(m['same_quality'])
            step_match = re.search(r'CRF\s*\+(\d+)', profile)
            if step_match and not profile.startswith("정밀"):
                value += int(step_match.group(1))
            self._suppress_sync = True
            try:
                val = max(18, min(45, value))
                self.crf_var.set(val)
                if val <= 23:
                    desc = "고화질·용량 큼"
                elif val <= 28:
                    desc = "표준 화질"
                elif val <= 35:
                    desc = "고압축·용량 절약"
                else:
                    desc = "초고압축·저화질"
                self.lbl_crf_val.config(text=f"{val:>2} · {desc}")
            finally:
                self._suppress_sync = False
            self.update_estimations()
        else:
            self.update_estimations()
        if mode == 'auto_precise' and self.file_list and not self.precise_quality_running:
            self.start_precise_quality_analysis([
                item for item in self.file_list
                if item.get('status') != "완료" and item.get('crf_mode') == 'auto_precise'
            ])

    def _strip_geometry_args(self, args):
        """이미 출력 해상도/FPS로 만든 기준 클립에 중복 적용될 -vf/-r을 제거한다."""
        result = []
        i = 0
        while i < len(args):
            if args[i] in ('-vf', '-r') and i + 1 < len(args):
                i += 2
                continue
            result.append(args[i])
            i += 1
        return result

    def _quality_reference_filter(self):
        filters = []
        res = self.combo_res.get()
        tw, th, vf_scale, _ = self.parse_resolution_setting(res)
        fit_choice = self.combo_merge_fit.get() if hasattr(self, 'combo_merge_fit') and self.combo_merge_fit else ""

        if vf_scale:
            if tw and th and ("꽉 채우기" in fit_choice or "Cover" in fit_choice):
                filters.append(f"scale={tw}:{th}:force_original_aspect_ratio=increase,crop={tw}:{th}")
            elif tw and th and ("자동 맞춤" in fit_choice or "Contain" in fit_choice):
                filters.append(f"scale={tw}:{th}:force_original_aspect_ratio=decrease,pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2")
            elif tw and th and ("가운데 정렬" in fit_choice or "Center" in fit_choice):
                filters.append(f"crop='min(iw,{tw})':'min(ih,{th})',pad={tw}:{th}:({tw}-iw)/2:({th}-ih)/2")
            else:
                filters.append(vf_scale)
        fps = self.combo_fps.get()
        if fps != "원본 유지":
            filters.append(f'fps={fps}')
        filters.append('format=yuv420p')
        return ','.join(filters)

    def _quality_snapshot(self):
        """Tk 값을 메인 스레드에서 읽어 정밀 분석 스레드에 전달한다."""
        args_by_crf = {
            crf: self._strip_geometry_args(self.build_video_encode_args(crf))
            for crf in range(18, 46)
        }
        sample_len = self.get_preview_duration()
        signature = '|'.join((
            self.combo_hw.get(), self.combo_codec.get(), self.combo_res.get(),
            self.combo_fps.get(), self._quality_reference_filter(),
            ' '.join(args_by_crf[28]), f'len={sample_len:.2f}',
        ))
        return {
            'args_by_crf': args_by_crf,
            'reference_filter': self._quality_reference_filter(),
            'sample_len': sample_len,
            'signature': signature,
        }

    def _quality_cache_key(self, item, snapshot):
        try:
            stat = os.stat(item['path'])
            file_sig = f"{stat.st_size}:{stat.st_mtime_ns}"
        except OSError:
            file_sig = f"{item.get('orig_size_b', 0)}:0"
        return f"{item['path']}|{file_sig}|{snapshot['signature']}"

    def start_precise_quality_analysis(self, items=None):
        """[v4.0] 무작위 위치 표본(미리보기 길이 초)의 VMAF/SSIM/PSNR 시험 인코딩을 시작한다."""
        if self.precise_quality_running:
            return
        if not self.ffmpeg_path:
            messagebox.showwarning("정밀 자동화질", "FFmpeg가 설치되어 있지 않아 정밀 분석을 시작할 수 없습니다.", parent=self.root)
            return
        targets = list(items if items is not None else self.file_list)
        targets = [item for item in targets if item.get('status') != "완료"]
        if not targets:
            self._set_auto_quality_status("자동화질 준비", "#6b7280")
            self.update_estimations()
            return
        try:
            snapshot = self._quality_snapshot()
        except Exception as e:
            messagebox.showerror("정밀 자동화질", f"시험 인코더 설정을 준비하지 못했습니다.\n{e}", parent=self.root)
            return
        pending = []
        for item in targets:
            key = self._quality_cache_key(item, snapshot)
            cur_mode = item.get('crf_mode')
            if not (isinstance(cur_mode, str) and cur_mode.startswith('auto_precise')):
                item['crf_mode'] = 'auto_precise'
            if item.get('precise_quality_key') != key or item.get('precise_crf') is None:
                pending.append((item, key))
        if not pending:
            self._set_auto_quality_status("자동화질 반영 완료", "#15803d")
            self.update_estimations()
            return
        self.precise_quality_running = True
        self.precise_quality_cancel = False
        self.precise_quality_generation += 1
        generation = self.precise_quality_generation
        self._set_auto_quality_status(f"▶ 정밀 계산 중 (0/{len(pending)})", "#b45309")
        btn = getattr(self, 'btn_cancel_precise', None)
        if btn is not None:
            btn.pack(side="left", padx=(4, 0))
        combo = getattr(self, 'combo_auto_quality', None)
        if combo is not None:
            combo.config(state="disabled")
        threading.Thread(
            target=self._run_precise_quality_analysis,
            args=(pending, snapshot, generation), daemon=True
        ).start()

    def _supports_libvmaf(self):
        if self.libvmaf_available_cache is not None:
            return self.libvmaf_available_cache
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        try:
            result = subprocess.run(
                [self.ffmpeg_path, '-hide_banner', '-filters'],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding='utf-8', errors='replace', timeout=30,
                creationflags=creationflags,
            )
            self.libvmaf_available_cache = bool(re.search(r'\blibvmaf\b', result.stdout or ''))
        except Exception:
            self.libvmaf_available_cache = False
        return self.libvmaf_available_cache

    def get_item_codec(self, item=None, gui_snapshot=None):
        """[v4.2] 해당 파일 항목의 개별 출력 코덱(설정 안 된 경우 전체 설정)을 반환한다 (스레드 안전)."""
        if item and isinstance(item, dict):
            mode = item.get('codec_mode', 'global')
            if mode and mode != 'global':
                return mode
        if gui_snapshot and 'combo_codec' in gui_snapshot:
            return gui_snapshot.get('combo_codec', '')
        if hasattr(self, 'combo_codec') and self.combo_codec:
            try:
                return self.combo_codec.get()
            except Exception:
                pass
        return ""

    def _run_quality_command(self, cmd, cwd=None, timeout=240):
        if self.precise_quality_cancel:
            return -1, '', 'cancelled'
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        proc = subprocess.Popen(
            cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', errors='replace', creationflags=creationflags,
        )
        self.precise_quality_process = proc
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            return proc.returncode, stdout or '', stderr or ''
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            return -1, stdout or '', (stderr or '') + '\n시간 제한 초과'
        finally:
            if self.precise_quality_process is proc:
                self.precise_quality_process = None

    def _make_quality_reference(self, item, start_sec, out_path, snapshot, clip_len=None):
        if clip_len is None:
            clip_len = float(snapshot.get('sample_len', 2.0))
        clip_len = min(max(0.10, clip_len), max(0.10, float(item.get('duration', 1.0))))
        cmd = [
            self.ffmpeg_path, '-hide_banner', '-loglevel', 'error', '-y',
            '-ss', f'{max(0.0, start_sec):.6f}', '-i', item['path'],
            '-t', f'{clip_len:.6f}', '-map', '0:v:0', '-an',
            '-vf', snapshot['reference_filter'], '-c:v', 'ffv1', '-level', '3', out_path,
        ]
        rc, _, err = self._run_quality_command(cmd, timeout=300)
        if rc != 0 or not os.path.exists(out_path):
            raise RuntimeError(f"원본 표본 생성 실패: {err.strip()[-500:]}")

    def _encode_quality_candidate(self, reference, out_path, crf, snapshot):
        """[v4.67] ultrafast 가속 옵션이 반영된 시험 인코딩"""
        cmd = [self.ffmpeg_path, '-hide_banner', '-loglevel', 'error', '-y', '-i', reference, '-an']
        raw_args = list(snapshot['args_by_crf'][int(crf)])
        fast_args = []
        skip_next = False
        for a in raw_args:
            if skip_next:
                skip_next = False
                continue
            if a == '-preset':
                fast_args.extend(['-preset', '10' if 'libsvtav1' in raw_args else 'ultrafast'])
                skip_next = True
            elif a == '-cpu-used':
                fast_args.extend(['-cpu-used', '8'])
                skip_next = True
            else:
                fast_args.append(a)
        if '-preset' not in raw_args and '-cpu-used' not in raw_args:
            if 'libsvtav1' in raw_args:
                fast_args.extend(['-preset', '10'])
            elif any(e in raw_args for e in ('libx264', 'libx265')):
                fast_args.extend(['-preset', 'ultrafast'])
        cmd.extend(fast_args)
        cmd.extend(['-pix_fmt', 'yuv420p', out_path])
        rc, _, err = self._run_quality_command(cmd, timeout=300)
        if rc != 0 or not os.path.exists(out_path):
            raise RuntimeError(f"CRF {crf} 시험 인코딩 실패: {err.strip()[-500:]}")

    def _measure_quality_pair(self, compressed, reference, workdir, tag, use_vmaf):
        metrics = {'vmaf': None, 'ssim': None, 'psnr': None}
        if use_vmaf:
            log_name = f'vmaf_{tag}.json'
            log_path = os.path.join(workdir, log_name)
            try:
                if os.path.exists(log_path):
                    os.remove(log_path)
            except OSError:
                pass
            cmd = [
                self.ffmpeg_path, '-hide_banner', '-loglevel', 'info',
                '-i', compressed, '-i', reference,
                '-lavfi', f'libvmaf=log_fmt=json:log_path={log_name}',
                '-f', 'null', '-' if os.name != 'nt' else 'NUL',
            ]
            rc, _, err = self._run_quality_command(cmd, cwd=workdir, timeout=300)
            if rc == 0 and os.path.exists(log_path):
                try:
                    data = json.loads(Path(log_path).read_text(encoding='utf-8'))
                    metrics['vmaf'] = float(data['pooled_metrics']['vmaf']['mean'])
                except Exception:
                    pass

        null_out = '-' if os.name != 'nt' else 'NUL'
        cmd_ssim = [
            self.ffmpeg_path, '-hide_banner', '-i', compressed, '-i', reference,
            '-lavfi', '[0:v][1:v]ssim', '-f', 'null', null_out,
        ]
        _, _, err_ssim = self._run_quality_command(cmd_ssim, timeout=240)
        match = re.search(r'All:([0-9.]+)', err_ssim)
        if match:
            metrics['ssim'] = float(match.group(1))

        cmd_psnr = [
            self.ffmpeg_path, '-hide_banner', '-i', compressed, '-i', reference,
            '-lavfi', '[0:v][1:v]psnr', '-f', 'null', null_out,
        ]
        _, _, err_psnr = self._run_quality_command(cmd_psnr, timeout=240)
        match = re.search(r'average:([0-9.]+|inf)', err_psnr, re.IGNORECASE)
        if match:
            metrics['psnr'] = float('inf') if match.group(1).lower() == 'inf' else float(match.group(1))
        return metrics

    def _quality_metrics_pass(self, metrics, use_vmaf):
        if use_vmaf and metrics.get('vmaf') is not None:
            vmaf_ok = metrics['vmaf'] >= self.VMAF_TARGET
            structural_ok = ((metrics.get('ssim') is not None and metrics['ssim'] >= 0.950)
                             or (metrics.get('psnr') is not None and metrics['psnr'] >= self.PSNR_TARGET))
            return vmaf_ok and structural_ok
        return (metrics.get('ssim') is not None and metrics['ssim'] >= self.SSIM_TARGET
                and metrics.get('psnr') is not None and metrics['psnr'] >= self.PSNR_TARGET)

    def _evaluate_quality_crf(self, refs, crf, snapshot, workdir, use_vmaf, progress_text):
        pair_metrics = []
        for index, reference in enumerate(refs):
            if self.precise_quality_cancel:
                raise RuntimeError("사용자 취소")
            self.root.after(0, self._set_auto_quality_status,
                            f"{progress_text} · CRF {crf}", "#b45309")
            candidate = os.path.join(workdir, f'candidate_{crf}_{index}.mkv')
            self._encode_quality_candidate(reference, candidate, crf, snapshot)
            metrics = self._measure_quality_pair(
                candidate, reference, workdir, f'{crf}_{index}', use_vmaf)
            pair_metrics.append(metrics)
            try:
                os.remove(candidate)
            except OSError:
                pass
        passed = all(self._quality_metrics_pass(m, use_vmaf) for m in pair_metrics)
        summary = {}
        for key in ('vmaf', 'ssim', 'psnr'):
            values = [m[key] for m in pair_metrics if m.get(key) is not None]
            summary[key] = min(values) if values else None
        return passed, summary

    def _find_precise_crf(self, item, snapshot, workdir, use_vmaf, progress_text):
        """[v4.52] 파일 길이 안에서 미리보기 길이를 1/2로 나눈 초 길이로 무작위 위치 2곳을 추출하여
        이진 탐색으로 화질 기준을 통과하는 가장 높은 CRF를 찾는다."""
        duration = max(0.1, float(item.get('duration', 0.1)))
        preview_sec = float(snapshot.get('sample_len', 2.0))
        # 미리보기 길이에 설정된 초 값을 1/2로 나누어 표본 길이로 사용
        half_sample_len = max(0.2, preview_sec / 2.0)
        sample_len = min(half_sample_len, duration)
        max_start = max(0.0, duration - sample_len)
        if max_start <= 0.0:
            starts = [0.0]
        else:
            # 전반/후반에서 각각 1곳씩 무작위로 뽑아 무작위 2곳 작업
            starts = [random.uniform(0.0, max_start / 2.0),
                      random.uniform(max_start / 2.0, max_start)]
        refs = []
        for index, start in enumerate(starts):
            ref_path = os.path.join(workdir, f'reference_{index}.mkv')
            self._make_quality_reference(item, start, ref_path, snapshot, sample_len)
            refs.append(ref_path)

        low, high = 18, 45
        best_crf = None
        best_metrics = None
        
        step = 0
        max_steps = 5 # 45-18=27, log2(27) is about 4.75
        
        while low <= high and not self.precise_quality_cancel:
            step += 1
            pct = min(99, int((step / max_steps) * 100))
            item['precise_sampling_progress'] = pct
            self.root.after(0, self.update_estimations)
            
            mid = (low + high) // 2
            passed, metrics = self._evaluate_quality_crf(
                refs, mid, snapshot, workdir, use_vmaf, progress_text)
            if passed:
                best_crf, best_metrics = mid, metrics
                low = mid + 1
            else:
                high = mid - 1

        if best_crf is None:
            p = self.estimate_file_params(item)
            best_crf = max(18, min(45, round(p['crf_same_quality']) if p else self.crf_var.get()))
        return best_crf, best_metrics

    def _run_precise_quality_analysis(self, pending, snapshot, generation):
        use_vmaf = self._supports_libvmaf()
        engine = "VMAF+SSIM+PSNR" if use_vmaf else "SSIM+PSNR 대체"
        failures = 0
        temp_root = tempfile.mkdtemp(prefix='svc_quality_')
        try:
            total = len(pending)
            start_time = time.time()
            for number, (item, cache_key) in enumerate(pending, 1):
                if self.precise_quality_cancel or generation != self.precise_quality_generation:
                    break
                safe_name = os.path.basename(item.get('name', 'video'))[:18]
                
                pct = int(((number - 1) / total) * 100)
                elapsed = time.time() - start_time
                completed = number - 1
                if completed > 0 and elapsed > 0:
                    avg_per_item = elapsed / completed
                    rem_sec = max(0, int(round(avg_per_item * (total - completed))))
                    eta_str = f"약 {self.format_time(rem_sec)}"
                else:
                    eta_str = "계산 중..."

                progress = f"▶ 정밀 계산 {pct}% ({number}/{total} · 남음: {eta_str}) [{safe_name}]"
                self.root.after(0, self._set_auto_quality_status, progress, "#b45309")
                
                item['precise_sampling_active'] = True
                item['precise_sampling_progress'] = 0
                self.root.after(0, self.update_estimations)
                
                item_dir = os.path.join(temp_root, f'item_{number}')
                os.makedirs(item_dir, exist_ok=True)
                try:
                    crf, metrics = self._find_precise_crf(
                        item, snapshot, item_dir, use_vmaf, progress)
                    out_c = getattr(self, 'combo_codec', None).get() if getattr(self, 'combo_codec', None) else ""
                    saver_off = 5 if "AV1" in out_c else 2
                    max_c = self.get_max_crf()
                    int_crf = int(crf)
                    item['precise_crf'] = int_crf
                    item['precise_same_quality'] = int_crf
                    item['precise_same_size'] = min(max_c, int_crf + saver_off)
                    item['precise_save_space'] = min(max_c, int_crf + saver_off + 2)
                    item['precise_metrics'] = metrics or {}
                    item['precise_quality_key'] = cache_key
                except Exception as e:
                    failures += 1
                    item['precise_error'] = str(e)
                finally:
                    item['precise_sampling_active'] = False
                self.root.after(0, self.update_estimations)
                self.root.after(0, self.draw_crf_markers)
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)
            self.root.after(0, self._finish_precise_quality_analysis,
                            generation, engine, failures, len(pending))

    def _finish_precise_quality_analysis(self, generation, engine, failures, total):
        if generation != self.precise_quality_generation:
            return
        self.precise_quality_running = False
        self.precise_quality_process = None
        combo = getattr(self, 'combo_auto_quality', None)
        if combo is not None:
            combo.config(state="readonly")
        btn = getattr(self, 'btn_cancel_precise', None)
        if btn is not None:
            btn.pack_forget()
        if self.precise_quality_cancel:
            self._set_auto_quality_status("▶ 정밀 계산 중지됨", "#b91c1c")
        elif failures:
            self._set_auto_quality_status(
                f"자동화질 일부 반영 ({total - failures}/{total} · {engine})", "#b45309")
        else:
            self._set_auto_quality_status(f"자동화질 반영 완료 ({engine})", "#15803d")
        self._refresh_auto_quality_profile_options()
        self.update_estimations()

    def cancel_precise_quality_analysis(self):
        self.precise_quality_cancel = True
        self.precise_quality_generation += 1
        proc = self.precise_quality_process
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
        self.precise_quality_running = False
        self.precise_quality_process = None
        combo = getattr(self, 'combo_auto_quality', None)
        if combo is not None:
            combo.config(state="readonly")
        btn = getattr(self, 'btn_cancel_precise', None)
        if btn is not None:
            btn.pack_forget()
        self._set_auto_quality_status("▶ 정밀 계산 중지됨", "#b91c1c")
        self.update_estimations()

    def draw_crf_markers(self, *args):
        c = getattr(self, 'crf_marker_canvas', None)
        c_top = getattr(self, 'crf_top_canvas', None)
        if not c or not c_top:
            return
        c.delete('all')
        c_top.delete('all')
        try:
            width = self.scale_crf.winfo_width()
            off = self.scale_crf.winfo_rootx() - c.winfo_rootx()
            off_top = self.scale_crf.winfo_rootx() - c_top.winfo_rootx()
        except Exception:
            return
        if width <= 1:
            c.after(300, self.draw_crf_markers)
            return

        pad = 8  # sliderlength 16의 절반(손잡이 반지름)
        lo = 18
        hi = self.get_max_crf()

        def x_of(v):
            vv = max(lo, min(hi, v))
            try:
                coords = self.scale_crf.coords(vv)
                if coords:
                    return off + coords[0]
            except Exception:
                pass
            return off + pad + (vv - lo) / (hi - lo) * (width - 2 * pad)

        def x_of_top(v):
            vv = max(lo, min(hi, v))
            try:
                coords = self.scale_crf.coords(vv)
                if coords:
                    return off_top + coords[0]
            except Exception:
                pass
            return off_top + pad + (vv - lo) / (hi - lo) * (width - 2 * pad)

        # [v4.52] AV1 코덱 선택 시 CRF 수치 체계(+7 오프셋)에 맞춘 추천 마커 및 배경 게이지 동적 조정
        combo_val = getattr(self, 'combo_codec', None).get() if getattr(self, 'combo_codec', None) else ""
        is_av1 = "AV1" in combo_val

        if is_av1:
            quality_regions = [
                (18, 31, "#dcfce7", "#16a34a"),  # 짙은 녹색 (최고화질/원본급)
                (31, 38, "#ecfccb", "#84cc16"),  # 연두색 (균형 추천)
                (38, 45, "#fef9c3", "#eab308"),  # 노란색 (고강도 절약)
                (45, 52, "#ffedd5", "#f97316"),  # 주황색 (극강 초고압축)
                (52, 58, "#fef2f2", "#ef4444"),  # 분홍/빨강 (컴팩트 보관)
                (58, 63, "#fee2e2", "#991b1b"),  # 짙은 빨강 (규격 최댓값)
            ]
            static_markers = [
                (24.0, "24", "원본급", "#15803d"),
                (31.0, "31", "고화질", "#15803d"),
                (35.0, "35", "표준", "#4d7c0f"),
                (42.0, "42", "고강도절약", "#a16207"),
                (50.0, "50", "초고압축", "#c2410c"),
                (56.0, "56", "컴팩트", "#b91c1c"),
                (63.0, "63", "최댓값", "#7f1d1d"),
            ]
        else:
            quality_regions = [
                (18, 23, "#dcfce7", "#16a34a"),  # 짙은 녹색 (고화질)
                (23, 28, "#ecfccb", "#84cc16"),  # 연두색 (표준)
                (28, 35, "#fef9c3", "#eab308"),  # 노란색 (절약)
                (35, 45, "#ffedd5", "#f97316"),  # 주황색 (고압축)
            ]
            static_markers = [
                (18.0, "18", "무손실급", "#15803d"),
                (23.0, "23", "고화질", "#15803d"),
                (28.0, "28", "표준", "#4d7c0f"),
                (33.0, "33", "절약", "#a16207"),
                (38.0, "38", "저용량", "#c2410c"),
                (43.0, "43", "최대압축", "#c2410c"),
            ]

        markers = []
        top_markers = []

        m = self.compute_marker_crfs()
        if m:
            if m.get('same_size') is not None:
                v = float(max(lo, min(hi, round(m['same_size']))))
                num_s = str(int(v))
                desc_s = "동일 용량\n▼"
                markers.append((v, num_s, "", "#dc2626", True))
                top_markers.append((v, desc_s, "#dc2626"))
            if m.get('same_quality') is not None:
                v = float(max(lo, min(hi, round(m['same_quality']))))
                num_s = str(int(v))
                desc_s = "동일 화질\n▼"
                markers.append((v, num_s, "", "#2563eb", True))
                top_markers.append((v, desc_s, "#2563eb"))

                # 동일화질 대비 절약 추천 마커 (AV1은 +5, 기타 코덱은 +2)
                saver_off = 5 if is_av1 else 2
                v2 = v + saver_off
                if lo <= v2 <= hi:
                    num_s2 = str(int(v2))
                    desc_s2 = "절약 추천\n▼"
                    markers.append((v2, num_s2, "", "#0d9488", True))
                    top_markers.append((v2, desc_s2, "#0d9488"))

            if m.get('precise_avg') is not None:
                v = float(max(lo, min(hi, round(m['precise_avg']))))
                num_s = str(int(v))
                desc_s = "정밀 추천\n▼"
                markers.append((v, num_s, "", "#7c3aed", True))
                top_markers.append((v, desc_s, "#7c3aed"))
        else:
            c_top.create_text(max(4, off_top + pad), 4, anchor="nw", fill="#9ca3af",
                              text="※ 파일을 추가하면 동일 용량 / 동일 화질 / 절약 추천 기준점이 이곳에 표시됩니다.",
                              font=("맑은 고딕", 8))
            for v, num_s, desc_s, color in static_markers:
                x = x_of(v)
                c.create_line(x, 0, x, 5, fill=color, width=1)
                text_block = f"{num_s}\n{desc_s}"
                if x <= off + 20:
                    anchor = "nw"
                    justify = "left"
                    text_x = max(2, x)
                elif x >= width - 30:
                    anchor = "ne"
                    justify = "right"
                    text_x = min(width - 2, x)
                else:
                    anchor = "n"
                    justify = "center"
                    text_x = x
                c.create_text(text_x, 4, text=text_block, fill=color, anchor=anchor, justify=justify, font=("맑은 고딕", 7))
            return

        dynamic_vs = {t[0] for t in markers if t[4]}
        for v, num_s, desc_s, color in static_markers:
            if v in dynamic_vs:
                # 동적 마커 수치와 겹칠 경우 정적 마커 숫자 생략 후 설명만 동일 라인 높이에 표시
                markers.append((v, "", desc_s, color, False))
            else:
                markers.append((v, num_s, desc_s, color, False))

        markers.sort(key=lambda t: t[0])
        top_markers.sort(key=lambda t: t[0])

        for i, (v, num_s, desc_s, color, dynamic) in enumerate(markers):
            x = x_of(v)
            line_h = 6 if dynamic else 4
            c.create_line(x, 0, x, line_h, fill=color, width=2 if dynamic else 1)

            text_block = f"{num_s}\n{desc_s}" if (num_s and desc_s) else (desc_s if desc_s else num_s)
            y_pos = 4

            font_style = ("맑은 고딕", 8 if dynamic else 7, "bold" if dynamic else "normal")
            if x <= off + 20:
                anchor = "nw"
                justify = "left"
                text_x = max(2, x)
            elif x >= width - 30:
                anchor = "ne"
                justify = "right"
                text_x = min(width - 2, x)
            else:
                anchor = "n"
                justify = "center"
                text_x = x

            c.create_text(
                text_x, y_pos,
                text=text_block,
                fill=color,
                anchor=anchor,
                justify=justify,
                font=font_style
            )

        # 상단 캔버스에 그리기 (설명 라벨 - 캔버스 높이 34px에 맞춰 y_pos 32 및 anchor="s" 조절)
        for i, (v, desc_s, color) in enumerate(top_markers):
            x = x_of_top(v)
            y_pos = 32

            if x <= off_top + 20:
                anchor = "sw"
                justify = "left"
                text_x = max(2, x)
            elif x >= width - 30:
                anchor = "se"
                justify = "right"
                text_x = min(width - 2, x)
            else:
                anchor = "s"
                justify = "center"
                text_x = x

            font_style = ("맑은 고딕", 8, "bold")
            c_top.create_text(
                text_x, y_pos,
                text=desc_s,
                fill=color,
                anchor=anchor,
                justify=justify,
                font=font_style
            )

    # ==================================================================
    #  [v2.4] 파일 목록 내 개별 화질(CRF) 셀 편집기
    # ==================================================================
    # ==================================================================
    #  [v4.2] 파일 목록 내 개별 화질(CRF) / 개별 코덱 셀 편집기 및 이벤트
    # ==================================================================
    # [v4.65g] 기존 get_item_codec(인자 1개)는 상단 L3505의 gui_snapshot 지원 버전으로 대체됨

    def get_item_codec_display(self, item):
        """Treeview 목록 셀 표시용 코덱 라벨"""
        mode = item.get('codec_mode', 'global') if item else 'global'
        if mode and mode != 'global':
            return self._shorten_codec_name(mode)
        return f"전체({self._shorten_codec_name(self.combo_codec.get())})"

    @staticmethod
    def _shorten_codec_name(full_name):
        if not full_name:
            return ""
        if "H.265" in full_name or "HEVC" in full_name:
            return "H.265/HEVC"
        elif "H.264" in full_name:
            return "H.264"
        elif "AV1" in full_name:
            return "AV1"
        elif "VP9" in full_name:
            return "VP9"
        elif "MKV" in full_name:
            return "MKV 방식"
        return str(full_name)

    def _close_crf_combo(self):
        if hasattr(self, 'crf_combo_editor') and self.crf_combo_editor:
            try:
                self.crf_combo_editor.destroy()
            except Exception:
                pass
            self.crf_combo_editor = None

    def _close_codec_combo(self):
        if hasattr(self, '_active_codec_combo') and self._active_codec_combo:
            try:
                self._active_codec_combo.destroy()
            except Exception:
                pass
            self._active_codec_combo = None

    def _close_all_combos(self):
        self._close_crf_combo()
        self._close_codec_combo()
        self._hide_crf_tooltip()

    def toggle_all_checks(self):
        """[v4.51] 제목줄 체크박스 클릭 시 전체 선택 및 전체 선택 해제"""
        if not self.file_list:
            return
        uncompleted = [item for item in self.file_list if item.get('status') != "완료"]
        if not uncompleted:
            return
        all_checked = all(item.get('checked', False) for item in uncompleted)
        new_state = not all_checked
        chk_symbol = "☑" if new_state else "☐"
        for item in self.file_list:
            if item.get('status') != "완료":
                item['checked'] = new_state
                item['manually_checked'] = False
                self.tree.set(item['id'], "chk", chk_symbol)
        self.tree.heading("chk", text=chk_symbol)
        self.update_estimations()

    def _update_chk_header_state(self):
        """[v4.51] 개별 체크 상태 변화 시 헤더 체크박스 모양 반영"""
        if not self.file_list:
            self.tree.heading("chk", text="☐")
            return
        uncompleted = [item for item in self.file_list if item.get('status') != "완료"]
        all_checked = all(item.get('checked', False) for item in uncompleted) if uncompleted else False
        self.tree.heading("chk", text="☑" if all_checked else "☐")

    def on_tree_click(self, event):
        self._close_all_combos()
        if self.is_running or self.precise_quality_running:
            return
        region = self.tree.identify('region', event.x, event.y)
        if region == 'heading':
            col_id = self.tree.identify_column(event.x)
            if col_id == '#1':
                self.toggle_all_checks()
                return "break"
            elif col_id == '#5':
                self.show_rotation_menu_selected()
                return "break"
            elif col_id == '#8':
                self._open_bulk_crf_menu(event)
                return "break"
            elif col_id == '#9':
                self._open_bulk_codec_menu(event)
                return "break"
            else:
                try:
                    col_idx = int(col_id.replace('#', '')) - 1
                    cols = ("chk", "name", "orig_codec", "orig_res", "rotate", "orig_bitrate", "orig_size",
                            "crf_sel", "result_codec", "size_info", "ratio_info", "status")
                    if 0 <= col_idx < len(cols):
                        self.sort_tree_column(cols[col_idx])
                except Exception:
                    pass
                return "break"
        elif region == 'cell':
            col_id = self.tree.identify_column(event.x)
            row_id = self.tree.identify_row(event.y)
            if not row_id:
                return

            if col_id == '#1':
                # 직접 체크박스 셀(#1)을 클릭한 경우 -> 개별 수동 체크/해제 (수동 선택으로 기억)
                item = next((f for f in self.file_list if f['id'] == row_id), None)
                if item and item.get('status') != "완료":
                    item['checked'] = not item.get('checked', False)
                    item['manually_checked'] = item['checked']
                    self.tree.set(row_id, "chk", "☑" if item['checked'] else "☐")
                    self._update_chk_header_state()
                    self.update_estimations()
            elif col_id == '#5':
                # [v4.61] 회전/반전 셀(#5)을 클릭한 경우 -> 90°(우)/90°(좌)/180°/좌우반전 순환 변경
                self.cycle_rotation(row_id)
            elif col_id == '#7':
                # [v4.65y] 목표 화질 셀(#7) 좌클릭 시 개별 화질/오프셋 콤보박스 편집기 호출
                self._open_item_crf_combo(row_id)
            else:
                # 파일명 등 다른 셀을 클릭하여 행을 선택한 경우: 단순 행 선택 유지 (체크박스 상태 보존)
                pass



    def sort_tree_column(self, col):
        """[v4.51] 제목줄 클릭 시 해당 열 기준 오름차순/내림차순 정렬"""
        if not self.file_list:
            return

        if getattr(self, '_sort_col', None) == col:
            self._sort_reverse = not getattr(self, '_sort_reverse', False)
        else:
            self._sort_col = col
            self._sort_reverse = False

        reverse = self._sort_reverse

        if col == "name":
            key_fn = lambda item: self._natural_sort_key(item.get('disp_name', item['name']))
        elif col == "orig_codec":
            key_fn = lambda item: item.get('orig_codec', '').lower()
        elif col == "orig_res":
            key_fn = lambda item: (item.get('orig_width', 0) * item.get('orig_height', 0))
        elif col == "orig_bitrate":
            key_fn = lambda item: item.get('orig_bitrate_b', 0)
        elif col == "orig_size":
            key_fn = lambda item: item.get('orig_size_b', 0)
        elif col == "size_info":
            def get_size_sort_key(item):
                if item.get('status') == "완료" and 'actual_size_b' in item:
                    return item['actual_size_b']
                return item.get('est_size_bytes', item.get('orig_size_b', 0))
            key_fn = get_size_sort_key
        elif col == "ratio_info":
            def get_ratio_sort_key(item):
                if item.get('status') == "완료" and 'actual_ratio' in item:
                    return item['actual_ratio']
                return item.get('est_ratio', 0)
            key_fn = get_ratio_sort_key
        elif col == "status":
            key_fn = lambda item: item.get('status', '')
        else:
            return

        self.file_list.sort(key=key_fn, reverse=reverse)

        for idx, item in enumerate(self.file_list):
            self.tree.move(item['id'], '', idx)

        base_headers = {
            "chk": "☐", "name": "파일명", "orig_codec": "원본 코덱",
            "orig_res": "원본 해상도", "orig_bitrate": "원본 비트레이트",
            "orig_size": "원본 크기", "crf_sel": "목표 화질 ▾",
            "result_codec": "결과 코덱 ▾", "size_info": "예상 파일 크기",
            "ratio_info": "예상 압축율", "status": "상태 및 남은 시간"
        }
        for c, base_txt in base_headers.items():
            if c == "chk":
                self._update_chk_header_state()
            elif c == col:
                arrow = " ▲" if not reverse else " ▼"
                self.tree.heading(c, text=base_txt + arrow)
            else:
                self.tree.heading(c, text=base_txt)

    def on_tree_double_click(self, event):
        """[v4.2] 더블클릭 영역별 분기:
        - #2~#6 (파일명 ~ 원본크기): 무작위 미리보기 실행
        - #7 (개별 화질 ▾): 파일별 개별 화질 드롭다운 편집기 열기
        - #8 (결과 코덱 ▾): 파일별 개별 코덱 드롭다운 편집기 열기
        """
        self._close_all_combos()
        if self.is_running or self.precise_quality_running:
            return "break"
        region = self.tree.identify('region', event.x, event.y)
        if region != 'cell':
            return "break"
        col_id = self.tree.identify_column(event.x)
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return "break"

        if col_id in ('#2', '#3', '#4', '#5', '#6'):
            self.start_queue_compare_preview(event)
        elif col_id == '#7':
            self._open_item_crf_combo(row_id)
        elif col_id == '#8':
            self._open_item_codec_combo(row_id)
        return "break"

    def _open_item_crf_combo(self, row_id):
        self._close_all_combos()
        item = next((f for f in self.file_list if f['id'] == row_id), None)
        if not item or item.get('status') == "완료":
            return
        bbox = self.tree.bbox(row_id, '#7')
        if not bbox:
            return
        x, y, w, h = bbox
        max_c = self.get_max_crf()
        values = (["전체 설정 따름"] + list(self.AUTO_QUALITY_PROFILES)
                  + list(self.PRECISE_OFFSET_PROFILES)
                  + [f"CRF {v}" for v in range(18, max_c + 1)])
        combo = ttk.Combobox(self.tree, values=values, state="readonly")
        combo.place(x=x, y=y, width=max(w, 250), height=h)
        mode = item.get('crf_mode', 'global')
        if mode == 'auto_q':
            combo.set("동일화질(보수적)")
        elif mode == 'auto_precise':
            combo.set("정밀추천(선택파일 샘플링)")
        elif isinstance(mode, str) and mode.startswith('auto_precise_off_'):
            off = self._precise_offset_from_mode(mode)
            match = next(
                (p for p in self.PRECISE_OFFSET_PROFILES
                 if self._precise_offset_from_mode(self.auto_profile_to_mode(p)) == off),
                None)
            combo.set(match or "정밀추천(선택파일 샘플링)")
        elif isinstance(mode, str) and mode.startswith('auto_plus_'):
            combo.set(f"추천 화질 대비 CRF +{mode.rsplit('_', 1)[-1]}")
        elif isinstance(mode, int):
            combo.set(f"CRF {mode}")
        else:
            combo.set("전체 설정 따름")

        def apply(_e=None):
            sel = combo.get()
            if sel == "전체 설정 따름":
                item['crf_mode'] = 'global'
            elif sel in self.AUTO_QUALITY_PROFILES or sel in self.PRECISE_OFFSET_PROFILES:
                item['crf_mode'] = self.auto_profile_to_mode(sel)
            else:
                m = re.search(r'CRF\s+(\d+)', sel)
                item['crf_mode'] = int(m.group(1)) if m else 'global'
            self._close_crf_combo()
            mode_now = item.get('crf_mode')
            if isinstance(mode_now, str) and mode_now.startswith('auto_precise'):
                self.start_precise_quality_analysis([item])
            else:
                self.update_estimations()

        combo.bind("<<ComboboxSelected>>", apply)
        combo.bind("<FocusOut>", lambda e: self._close_crf_combo())
        combo.bind("<Escape>", lambda e: self._close_crf_combo())
        combo.focus_set()
        self.crf_combo_editor = combo

    def _open_item_codec_combo(self, row_id):
        self._close_all_combos()
        item = next((f for f in self.file_list if f['id'] == row_id), None)
        if not item or item.get('status') == "완료":
            return
        bbox = self.tree.bbox(row_id, '#8')
        if not bbox:
            return
        x, y, w, h = bbox
        values = ["전체 설정 따름",
                  "H.265/HEVC (고압축, 추천)",
                  "H.264 (표준, 호환성)",
                  "AV1 (차세대 초고압축)",
                  "VP9 (웹 호환성)",
                  "MKV 방식 (Matroska - 자막/다중트랙 보존)"]
        combo = ttk.Combobox(self.tree, values=values, state="readonly")
        combo.place(x=x, y=y, width=max(w, 240), height=h)
        current_mode = item.get('codec_mode', 'global')
        if current_mode == 'global' or not current_mode:
            combo.set("전체 설정 따름")
        else:
            combo.set(current_mode)

        def apply(_e=None):
            sel = combo.get()
            if sel == "전체 설정 따름":
                item['codec_mode'] = 'global'
            else:
                item['codec_mode'] = sel
            self._close_codec_combo()
            self.update_estimations()

        combo.bind("<<ComboboxSelected>>", apply)
        combo.bind("<FocusOut>", lambda e: self._close_codec_combo())
        combo.bind("<Escape>", lambda e: self._close_codec_combo())
        combo.focus_set()
        self._active_codec_combo = combo

    def _open_bulk_codec_menu(self, event):
        if self.is_running or self.precise_quality_running or not self.file_list:
            return
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="[전체 파일] 기본 (전체 설정 따름)",
                         command=lambda: self._apply_bulk_codec('global'))
        menu.add_separator()
        codecs = [
            "H.265/HEVC (고압축, 추천)",
            "H.264 (표준, 호환성)",
            "AV1 (차세대 초고압축)",
            "VP9 (웹 호환성)",
            "MKV 방식 (Matroska - 자막/다중트랙 보존)"
        ]
        for c in codecs:
            menu.add_command(label=f"[전체 파일] {c}",
                             command=lambda val=c: self._apply_bulk_codec(val))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _open_file_folder(self, filepath):
        """[v4.52] 파일이 위치한 폴더를 열고 해당 파일을 선택한다."""
        if not filepath:
            return
        p = Path(filepath)
        if p.exists():
            if os.name == 'nt':
                subprocess.Popen(f'explorer /select,"{os.path.normpath(str(p))}"')
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', '-R', str(p)])
            else:
                subprocess.Popen(['xdg-open', str(p.parent)])
        elif p.parent.exists():
            if os.name == 'nt':
                os.startfile(str(p.parent))
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', str(p.parent)])
            else:
                subprocess.Popen(['xdg-open', str(p.parent)])
        else:
            messagebox.showinfo("안내", f"폴더를 찾을 수 없습니다:\n{p.parent}", parent=self.root)

    def _open_result_folder(self, out_filepath, item):
        """[v4.52] 결과 파일이 저장될/저장된 폴더를 탐색기에서 연다."""
        target_dir = self.get_target_dir(item) or (Path(item['path']).parent if item.get('path') else None)
        if out_filepath and os.path.exists(out_filepath):
            self._open_file_folder(out_filepath)
        elif target_dir and os.path.exists(target_dir):
            if os.name == 'nt':
                os.startfile(os.path.normpath(str(target_dir)))
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', str(target_dir)])
            else:
                subprocess.Popen(['xdg-open', str(target_dir)])
        else:
            messagebox.showinfo("안내", "결과 파일 저장 폴더가 아직 생성되지 않았습니다.", parent=self.root)

    def on_tree_right_click(self, event):
        """[v4.52] 목록 우클릭 컨텍스트 메뉴: 원본/결과 폴더 열기, 원본/결과 동영상 재생, 샘플링 미리보기, 선택 삭제"""
        if getattr(self, '_suppress_sync', False):
            return
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return

        if row_id not in self.tree.selection():
            self.tree.selection_set(row_id)
            self.tree.focus(row_id)
            self.on_tree_select(None)

        item = next((f for f in self.file_list if f['id'] == row_id), None)
        if not item:
            return

        orig_path = item.get('path', '')
        eff_crf = self.get_effective_crf(item)
        out_path = item.get('out_path') or (str(self.get_output_path(orig_path, eff_crf, item)) if orig_path else None)

        menu = tk.Menu(self.root, tearoff=0)

        # 1) 원본 파일 폴더 열기
        menu.add_command(
            label="📁 원본 파일 폴더 열기",
            command=lambda p=orig_path: self._open_file_folder(p)
        )

        # 2) 결과 파일 폴더 열기
        menu.add_command(
            label="📂 결과 파일 폴더 열기",
            command=lambda p=out_path, it=item: self._open_result_folder(p, it)
        )

        menu.add_separator()

        # 3) 원본 동영상 재생
        menu.add_command(
            label="▶️ 원본 동영상 재생",
            command=lambda p=orig_path: self.open_with_default_player(p)
        )

        # 4) 결과 동영상 재생 (인코딩이 완료되고 파일이 존재하는 경우에만 표시 및 동작)
        is_completed = item.get('status') == "완료" or (isinstance(item.get('status'), str) and "완료" in item.get('status'))
        res_file_exists = out_path and os.path.exists(out_path)
        if is_completed and res_file_exists:
            menu.add_command(
                label="🎬 결과 동영상 재생",
                command=lambda p=out_path: self.open_with_default_player(p)
            )

        # 5) 샘플링 하여 미리보기
        menu.add_command(
            label="🎞️ 샘플링 하여 미리보기",
            command=lambda it=item: self.start_preview(it)
        )

        menu.add_separator()

        # [v4.61] 회전 / 좌우 반전 설정 서브메뉴
        rot_menu = tk.Menu(menu, tearoff=0)
        rot_menu.add_command(label="🔄 0° (회전 없음 / 기본)", command=lambda: self.set_selected_rotation('0'))
        rot_menu.add_command(label="↷ 오른쪽 90° 회전 (시계 방향)", command=lambda: self.set_selected_rotation('90_cw'))
        rot_menu.add_command(label="↶ 왼쪽 90° 회전 (반시계 방향)", command=lambda: self.set_selected_rotation('90_ccw'))
        rot_menu.add_command(label="🙃 180° 회전", command=lambda: self.set_selected_rotation('180'))
        rot_menu.add_command(label="↔️ 좌우 반전 (Horizontal Flip)", command=lambda: self.set_selected_rotation('hflip'))
        menu.add_cascade(label="🔄 영상 회전 및 좌우 반전 설정", menu=rot_menu)

        menu.add_separator()

        # 6) 선택 항목 삭제
        menu.add_command(
            label="🗑️ 선택 항목 삭제",
            command=self.remove_selected,
            state="disabled" if self.is_running else "normal"
        )

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    @staticmethod
    def format_ratio_display(ratio_pct):
        """[v4.51] 압축율 수치(+/- 및 % 뒤 전각 표식 ▼/▲/─) 포맷"""
        if ratio_pct > 0.05:
            return f"-{ratio_pct:.1f}% ▼"
        elif ratio_pct < -0.05:
            return f"+{abs(ratio_pct):.1f}% ▲"
        else:
            return "0.0% ─"

    def get_size_gauge_info(self, est_bytes, orig_bytes):
        """[v4.5] 예상 파일 크기 및 게이지 색상 태그를 반환한다."""
        if orig_bytes <= 0:
            return "0 MB", "0.0% ─", "gauge_yellow"

        ratio = ((orig_bytes - est_bytes) / orig_bytes) * 100

        if est_bytes >= orig_bytes:
            tag = "gauge_red"
        else:
            if ratio <= 5.0:
                tag = "gauge_orange"
            elif ratio <= 30.0:
                tag = "gauge_yellow"
            elif ratio <= 50.0:
                tag = "gauge_lime"
            else:
                tag = "gauge_green"

        return self.format_size(est_bytes), self.format_ratio_display(ratio), tag

    def get_crf_sel_display(self, item, eff_crf):
        """[v4.65y] 목표 화질 셀에 표시할 텍스트 포맷. 사용자가 요청한 오프셋 및 간결 표시 포맷 적용."""
        mode = item.get('crf_mode', 'auto_q')
        
        if mode == 'custom' or isinstance(mode, int) or (isinstance(mode, str) and mode.startswith('selected_file')):
            return f"직접선택({eff_crf})"
            
        if isinstance(mode, str) and (mode.startswith('auto_off_') or mode.startswith('auto_precise_off_')):
            try:
                off = int(mode.rsplit('_', 1)[-1])
                is_p = mode.startswith('auto_precise_off_')
                prefix = "정밀추천_화질" if is_p else "추천_화질"
                off_str = f"{off:+d}"
                base_crf = eff_crf - off
                return f"{prefix}({base_crf}) {off_str}"
            except ValueError:
                pass

        if mode in ('precise_same_size', 'precise_green'): return f"정밀추천_용량({eff_crf})"
        if mode in ('precise_same_quality', 'precise_blue', 'precise_purple') or (isinstance(mode, str) and mode.startswith('auto_precise')): return f"정밀추천_화질({eff_crf})"
        if mode == 'precise_save_space': return f"정밀추천_절약({eff_crf})"
        
        if mode == 'auto_same_size': return f"추천_용량({eff_crf})"
        if mode == 'auto_q' or (isinstance(mode, str) and mode.startswith('auto_plus_')): return f"추천_화질({eff_crf})"
        if mode == 'auto_save_space': return f"추천_절약({eff_crf})"
        
        return f"추천_화질({eff_crf})"

    def update_estimations(self, event=None):
        # [v4.65p FIX] 원본 폴더와 동일한 폴더 + 기존 파일명 유지 + 출력 포맷까지 동일할 경우 '작업 완료 후 원본 삭제' 자동 체크
        if hasattr(self, 'output_mode') and hasattr(self, 'filename_mode_var') and hasattr(self, 'delete_orig_file') and hasattr(self, 'combo_format'):
            if self.output_mode.get() == 'source':
                fmode = self.filename_mode_var.get()
                if "기존 파일명" in fmode:
                    out_fmt = self.combo_format.get()
                    import re
                    m = re.search(r'\(\.(.+?)\)', out_fmt)
                    if m:
                        out_ext = "." + m.group(1).lower()
                        if hasattr(self, 'file_list') and self.file_list:
                            # 큐에 있는 모든 파일의 원본 확장자가 선택된 출력 확장자와 동일한지 검사
                            if all(Path(f['path']).suffix.lower() == out_ext for f in self.file_list):
                                self.delete_orig_file.set(True)

        if not hasattr(self, 'file_list'):
            return

        total_orig_size = 0
        total_est_size = 0
        total_rem_time = 0.0
        total_duration = 0.0

        for item in self.file_list:
            total_orig_size += item['orig_size_b']
            total_duration += float(item.get('duration', 0) or 0)
            eff_crf = self.get_effective_crf(item)

            if item.get('status') == "완료" and 'actual_size_b' in item:
                act_bytes = item['actual_size_b']
                orig_b = item['orig_size_b']
                act_ratio = ((orig_b - act_bytes) / orig_b * 100) if orig_b > 0 else 0
                item['actual_ratio'] = act_ratio

                size_str = self.format_size(act_bytes)
                ratio_str = self.format_ratio_display(act_ratio)
                gauge_tag = "gauge_green" if act_ratio >= 0 else "gauge_red"
                total_est_size += act_bytes
            else:
                est_size_bytes, est_time_sec = self.estimate_item_size_and_time(item, eff_crf)
                item['est_size_bytes'] = est_size_bytes
                item['est_time_sec'] = est_time_sec
                orig_b = item['orig_size_b']
                est_ratio = ((orig_b - est_size_bytes) / orig_b * 100) if orig_b > 0 else 0
                item['est_ratio'] = est_ratio

                total_est_size += est_size_bytes
                if "대기 중" in item['status']:
                    total_rem_time += est_time_sec

                size_str, ratio_str, gauge_tag = self.get_size_gauge_info(est_size_bytes, item['orig_size_b'])
                
                # [v4.65x] 실시간 샘플링 상태 표시
                if item.get('precise_sampling_active'):
                    pct = item.get('precise_sampling_progress', 0)
                    size_str = f"샘플링 중 ({pct}%)"
                    ratio_str = "-"
                elif item.get('precise_crf') is not None and item.get('crf_mode', '').startswith('precise'):
                    size_str = f"[샘플링 완료] {size_str}"

            item_id = item['id']
            if self.tree.exists(item_id):
                try:
                    self.tree.set(item_id, "crf_sel", self.get_crf_sel_display(item, eff_crf))
                    self.tree.set(item_id, "result_codec", self.get_item_codec_display(item))
                    self.tree.set(item_id, "size_info", size_str)
                    self.tree.set(item_id, "ratio_info", ratio_str)

                    if "대기 중" in item['status']:
                        time_str = self.format_time(item.get('est_time_sec', 0))
                        new_status = f"대기 중 (예상 {time_str})"
                        item['status'] = new_status
                        self.tree.set(item_id, "status", new_status)
                        self.tree.item(item_id, tags=(gauge_tag,))
                except Exception as e:
                    print(f"tree update error: {e}")

        self.update_summary_panel(total_orig_size, total_est_size, total_rem_time, total_duration)
        self.draw_crf_markers()



    def _apply_bulk_codec(self, val):
        for f in self.file_list:
            if f.get('status') != "완료":
                f['codec_mode'] = val
        self.update_estimations()

    def on_tree_select(self, event=None):
        """[v4.5] 대기열의 파일 선택 시 하단 인코딩 상세 설정 컨트롤을 해당 파일의 값으로 동기화한다."""
        if getattr(self, '_suppress_sync', False) or not hasattr(self, 'file_list'):
            return
        selected_ids = self.tree.selection()
        if not selected_ids:
            return
        selected_item = next((f for f in self.file_list if f['id'] == selected_ids[0]), None)
        if not selected_item:
            return

        self._suppress_sync = True
        try:
            eff_crf = self.get_effective_crf(selected_item)
            self.crf_var.set(eff_crf)
            self.on_crf_change(None)

            c_mode = selected_item.get('codec_mode') or 'global'
            if hasattr(self, 'combo_codec'):
                if c_mode != 'global':
                    self.combo_codec.set(c_mode)
                else:
                    self.combo_codec.current(0)

            r_mode = selected_item.get('res_mode') or 'global'
            if hasattr(self, 'combo_res'):
                if r_mode != 'global':
                    self.combo_res.set(r_mode)
                else:
                    self.combo_res.current(0)

            f_mode = selected_item.get('fps_mode') or 'global'
            if hasattr(self, 'combo_fps'):
                if f_mode != 'global':
                    self.combo_fps.set(f_mode)
                else:
                    self.combo_fps.current(0)

            a_mode = selected_item.get('audio_mode') or 'global'
            if hasattr(self, 'combo_audio'):
                if a_mode != 'global':
                    self.combo_audio.set(a_mode)
                else:
                    self.combo_audio.current(0)

            # [v4.51] 목록에서 단일 선택된 경우 화질 기준 드롭다운에 어떤 모드가 적용되어 있는지 동기화
            if len(selected_ids) == 1:
                crf_mode = selected_item.get('crf_mode')
                if crf_mode == 'custom' or isinstance(crf_mode, int):
                    self.auto_quality_profile_var.set("사용자 지정")
                elif crf_mode == 'auto_q':
                    self.auto_quality_profile_var.set("동일화질(보수적)")
                elif crf_mode == 'auto_precise':
                    self.auto_quality_profile_var.set("정밀추천(선택파일 샘플링)")
                elif crf_mode == 'precise_purple':
                    self.auto_quality_profile_var.set("정밀추천(기준 값)")
                elif crf_mode == 'precise_blue':
                    self.auto_quality_profile_var.set("정밀추천(동일 화질)")
                elif crf_mode == 'precise_green':
                    self.auto_quality_profile_var.set("정밀추천(용량 절약)")
                else:
                    self.auto_quality_profile_var.set("")
            else:
                self.auto_quality_profile_var.set("")
        finally:
            self._suppress_sync = False

    def sync_controls_to_selected_items(self, control_type, value):
        """[v4.51] 하단 인코딩 컨트롤 변경 시 선택/체크된 항목에 설정을 반영하며,
        아무것도 선택/체크되지 않은 경우 목록 전체를 자동 체크(☑)하고 일괄 적용한다."""
        if getattr(self, '_suppress_sync', False) or not hasattr(self, 'file_list'):
            return
            
        selected_ids = set(self.tree.selection())
        
        # 1. 현재 체크되어 있거나 표에서 행이 선택/강조된 항목 찾기
        target_items = [
            f for f in self.file_list 
            if f.get('status') != "완료" and (f.get('checked', False) or f['id'] in selected_ids)
        ]
        
        # 2. 체크되거나 선택된 항목이 전혀 없다면 대기열 전체를 자동으로 체크(☑) 처리!
        if not target_items:
            target_items = [f for f in self.file_list if f.get('status') != "완료"]
            if not target_items:
                return
            for item in target_items:
                item['checked'] = True
                self.tree.set(item['id'], "chk", "☑")
            self._update_chk_header_state()

        # 3. 대상 항목들에 해당 컨트롤 값 반영
        for item in target_items:
            if control_type == 'crf':
                item['crf_mode'] = int(value)
                item['custom_crf'] = int(value)
            elif control_type == 'codec':
                item['codec_mode'] = value
            elif control_type == 'res':
                item['res_mode'] = value
            elif control_type == 'fps':
                item['fps_mode'] = value
            elif control_type == 'audio':
                item['audio_mode'] = value

        self.update_estimations()


    # ==================================================================
    #  [v4.0] '개별 화질' 헤더 클릭: 목록 전체 일괄 적용 메뉴
    #   - 현재 목록값 대비 상대 조정(-5 ~ +5, 용량 영향도 표시)
    #   - 일괄 CRF 직접 입력(18~45)
    # ==================================================================
    def _close_bulk_crf_menu(self):
        if getattr(self, 'bulk_crf_menu', None) is not None:
            try:
                self.bulk_crf_menu.destroy()
            except Exception:
                pass
            self.bulk_crf_menu = None

    def _open_bulk_crf_menu(self, event):
        """개별 화질 헤더 아래에 일괄 적용 드롭다운 메뉴를 띄운다."""
        self._close_bulk_crf_menu()
        targets = [f for f in self.file_list if f.get('status') != "완료"]
        if not targets:
            messagebox.showinfo("안내", "일괄 적용할 파일이 목록에 없습니다.", parent=self.root)
            return
        menu = tk.Menu(self.tree, tearoff=0)
        self.bulk_crf_menu = menu
        menu.add_command(label="전체 설정 따름 (개별 지정 모두 해제)",
                         command=lambda: self._bulk_apply_mode('global'))
        menu.add_command(label="동일화질(보수적) 자동 적용",
                         command=lambda: self._bulk_apply_mode('auto_q'))
        menu.add_command(label="정밀추천(선택파일 샘플링) 자동 적용",
                         command=lambda: self._bulk_apply_mode('auto_precise'))
        menu.add_separator()
        menu.add_command(label="─ 현재 목록값 대비 일괄 조정 ─", state="disabled")
        for delta in range(-5, 6):
            if delta == 0:
                continue
            ratio = (2 ** (-delta / 6.0) - 1) * 100  # CRF -1당 용량 약 +12%
            if delta < 0:
                desc = f"화질 향상▲ · 용량 약 +{ratio:.0f}% 증가"
            else:
                desc = f"화질 저하▼ · 용량 약 {ratio:.0f}% 감소"
            menu.add_command(label=f"CRF {delta:+d}  ({desc})",
                             command=lambda d=delta: self._bulk_adjust_crf(d))
        menu.add_separator()
        menu.add_command(label="일괄 CRF 직접 입력... (18~45 동일값 적용)",
                         command=self._bulk_set_crf_dialog)
        # 헤더 셀 바로 아래에 표시 (가로 스크롤 반영)
        try:
            bbox = self.tree.bbox(self.tree.get_children()[0], '#6') if self.tree.get_children() else None
        except Exception:
            bbox = None
        if bbox:
            x = self.tree.winfo_rootx() + bbox[0]
            y = self.tree.winfo_rooty() + max(0, bbox[1])
        else:
            x, y = event.x_root, event.y_root
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _bulk_targets(self):
        return [f for f in self.file_list if f.get('status') != "완료"]

    def _bulk_apply_mode(self, mode):
        """모든 미완료 항목에 동일 모드를 적용한다."""
        targets = self._bulk_targets()
        if not targets:
            return
        for item in targets:
            item['crf_mode'] = mode
        if isinstance(mode, str) and mode.startswith('auto_precise'):
            self.start_precise_quality_analysis(targets)
        else:
            self.update_estimations()
        self.lbl_stats.config(text=f"개별 화질 일괄 적용 완료 ({len(targets)}개 항목)")

    def _bulk_adjust_crf(self, delta):
        """[v4.0] 각 항목의 '현재 적용 CRF'에 delta를 더한 값을 수동 CRF로 고정한다."""
        targets = self._bulk_targets()
        if not targets:
            return
        max_c = self.get_max_crf()
        for item in targets:
            eff = self.get_effective_crf(item)
            item['crf_mode'] = max(18, min(max_c, int(eff) + int(delta)))
        self.update_estimations()
        self.lbl_stats.config(
            text=f"현재 목록값 대비 CRF {delta:+d} 일괄 조정 완료 ({len(targets)}개 항목, 범위 18~{max_c} 제한)")

    def _bulk_set_crf_dialog(self):
        """[v4.0] 목록 전체에 동일한 CRF 값을 직접 입력받아 적용한다."""
        targets = self._bulk_targets()
        if not targets:
            return
        max_c = self.get_max_crf()
        dlg = tk.Toplevel(self.root)
        dlg.title("일괄 CRF 직접 입력")
        self.center_window(dlg, 420, 160)
        dlg.transient(self.root)
        dlg.resizable(False, False)
        dlg.grab_set()
        tk.Label(dlg, text=f"목록 전체(완료 제외)에 적용할 CRF 값을 입력하세요. (18~{max_c})\n"
                           "값이 낮을수록 화질 향상▲·용량 증가▲, 높을수록 화질 저하▼·용량 감소▼",
                 justify="left", padx=14, pady=10).pack(anchor="w")
        row = ttk.Frame(dlg)
        row.pack(padx=14, pady=(0, 6), anchor="w")
        ttk.Label(row, text="CRF:").pack(side="left")
        val_var = tk.StringVar(value=str(self.crf_var.get()))
        try:
            spin = ttk.Spinbox(row, from_=18, to=max_c, width=6, textvariable=val_var)
        except AttributeError:
            spin = ttk.Spinbox(row, from_=18, to=max_c, width=6, textvariable=val_var)
        spin.pack(side="left", padx=(6, 0))
        hint = tk.Label(dlg, text="", fg="#2563eb", padx=14)
        hint.pack(anchor="w")

        def refresh_hint(*_a):
            try:
                v = int(float(val_var.get()))
                diff = v - (35 if max_c == 55 else 28)
                pct = (2 ** (-diff / 6.0) - 1) * 100
                hint.config(text=f"표준 대비 용량 약 {pct:+.0f}% (경험칙)")
            except Exception:
                hint.config(text="")
        val_var.trace_add('write', refresh_hint)
        refresh_hint()

        def apply_value(_e=None):
            try:
                v = int(float(val_var.get()))
            except Exception:
                messagebox.showwarning("입력 오류", f"18~{max_c} 사이의 숫자를 입력해주세요.", parent=dlg)
                return
            v = max(18, min(max_c, v))
            for item in targets:
                item['crf_mode'] = v
            dlg.destroy()
            self.update_estimations()
            self.lbl_stats.config(text=f"CRF {v} 일괄 적용 완료 ({len(targets)}개 항목)")

        btns = ttk.Frame(dlg)
        btns.pack(pady=(4, 12))
        ttk.Button(btns, text="일괄 적용", command=apply_value).pack(side="left", padx=5)
        ttk.Button(btns, text="취소", command=dlg.destroy).pack(side="left", padx=5)
        dlg.bind("<Return>", apply_value)
        dlg.bind("<Escape>", lambda e: dlg.destroy())
        spin.focus_set()
        dlg.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - dlg.winfo_width()) // 2
        y = self.root.winfo_rooty() + 200
        dlg.geometry(f"+{max(0, x)}+{max(0, y)}")




    def _preview_done_if_needed(self):
        """[v4.60] finally 안전망: 예외로 인해 _preview_done이 정상 실행되지 않았을 때 보완 호출."""
        if self.is_previewing:
            self._preview_done()

    def _preview_done(self):
        # 중복 호출 방지: 이미 완료된 경우 skip
        if not self.is_previewing and self._compare_encoding_item is None:
            # 버튼 상태만 재확인해서 혹시 남아있으면 복원
            try:
                self.btn_preview.config(state="normal", text="🎞️ 샘플링하여 미리보기")
            except Exception:
                pass
            return
        self.is_previewing = False
        # [v4.60 fix] 미리보기 완료 시 열려 있는 셀 편집기(콤보박스)를 강제 닫아
        # 첫 번째 행에 편집기가 남아 '체크박스가 커진 것처럼' 보이는 문제 방지
        try:
            self._close_all_combos()
        except Exception:
            pass
        item = self._compare_encoding_item
        self._compare_encoding_item = None
        if item is not None:
            try:
                prev = item.pop('pre_compare_status', None)
                restore_status = prev or item.get('status', '대기 중')
                if item.get('status') != "완료":
                    # [v4.60 fix] 트리 표시와 data dict 모두 복구
                    item['status'] = restore_status
                    self.tree.set(item['id'], "status", restore_status)
                # [v4.60 fix] processing 태그 명시적 해제 후 체크박스 표시 복원
                self.tree.item(item['id'], tags=())
                chk_sym = "☑" if item.get('checked', False) else "☐"
                self.tree.set(item['id'], "chk", chk_sym)
            except Exception:
                pass
        # [v4.60 fix] 헤더 체크박스 상태 갱신
        try:
            self._update_chk_header_state()
        except Exception:
            pass
        try:
            self.btn_preview.config(state="normal", text="🎞️ 샘플링하여 미리보기")
        except Exception:
            pass
        try:
            self.lbl_stats.config(text="미리보기 준비 완료" if self.preview_temp_dir else "대기 중...")
        except Exception:
            pass


    def _build_crf_tooltip_text(self, item):
        """[v3.4] 개별 화질 셀 호버 시 표시할 상세 정보."""
        p = self.estimate_file_params(item)
        base = max(18, min(45, round(p['crf_same_quality']) if p else self.crf_var.get()))
        precise = item.get('precise_crf')
        metrics = item.get('precise_metrics') or {}
        mode = item.get('crf_mode', 'global')
        eff = self.get_effective_crf(item)

        if mode == 'auto_q':
            mode_txt = "동일화질(보수적) 자동"
        elif isinstance(mode, str) and mode.startswith('auto_precise'):
            off = self._precise_offset_from_mode(mode)
            mode_txt = ("정밀 추천 자동" if not off
                        else f"정밀 추천 {off:+d} ({self._precise_offset_meaning(off)})")
        elif isinstance(mode, str) and mode.startswith('auto_plus_'):
            mode_txt = f"추천 화질 대비 +{mode.rsplit('_', 1)[-1]}"
        elif isinstance(mode, int):
            mode_txt = "수동 지정"
        else:
            mode_txt = "전체 설정 따름"

        lines = [f"현재 적용 CRF: {eff}   (모드: {mode_txt})", ""]
        lines.append(f"동일화질(보수적) 추천: CRF {base}")
        if precise is not None:
            parts = []
            try:
                if metrics.get('vmaf') is not None:
                    parts.append(f"VMAF {metrics['vmaf']:.1f}")
                if metrics.get('ssim') is not None:
                    parts.append(f"SSIM {metrics['ssim']:.3f}")
                if metrics.get('psnr') is not None and metrics['psnr'] != float('inf'):
                    parts.append(f"PSNR {metrics['psnr']:.1f}")
            except Exception:
                parts = []
            suffix = f"   ({' · '.join(parts)})" if parts else ""
            lines.append(f"정밀 추천: CRF {int(precise)}{suffix}")
            rec = int(precise)
        elif isinstance(mode, str) and mode.startswith('auto_precise'):
            lines.append("정밀 추천: 계산 중... (임시로 보수적 추천 기준 적용)")
            rec = base
        else:
            rec = base

        diff = eff - rec
        if diff:
            lines.append(f"추천 대비 변동: {diff:+d} ({self._precise_offset_meaning(diff)})")
        else:
            lines.append("추천 대비 변동: 없음 (추천값 그대로)")

        orig = item.get('orig_size_b', 0)
        est_rec = self.estimate_size_at_crf(item, rec)
        est_cur = self.estimate_size_at_crf(item, eff)
        lines.append("")
        lines.append(f"원본 용량: {self.format_size(orig)}")
        lines.append(f"추천 CRF {rec} 적용 시 예상: {self.format_size(est_rec)}")
        lines.append(f"현재 CRF {eff} 적용 시 예상: {self.format_size(est_cur)}")
        if est_rec > 0 and diff:
            pct = (est_cur / est_rec - 1) * 100
            lines.append(f"추천 대비 용량 변화: {pct:+.1f}%")
        lines.append("")
        lines.append("※ 경험칙: CRF 1단계 차이 ≈ 용량 약 ±12%")
        return "\n".join(lines)

    def _build_item_info_tooltip(self, item):
        """[v4.51] 목록 행 호버 시 파일 전체 정보 및 (완료 시) 실제 결과 vs 예상 비교 표시"""
        path = item.get('path', '')
        wrapped_path = "\n        ".join(path[i:i + 80] for i in range(0, len(path), 80)) if path else "-"
        vals = {}
        try:
            vals = dict(zip(
                ("chk", "name", "orig_codec", "orig_res", "orig_bitrate", "orig_size",
                 "crf_sel", "result_codec", "size_info", "ratio_info", "status"),
                self.tree.item(item['id'], 'values')))
        except Exception:
            pass

        dur = float(item.get('duration') or 0)
        eff_crf = self.get_effective_crf(item)
        orig_b = item.get('orig_size_b', 0)
        
        p = self.estimate_file_params(item)
        est_b, est_bps = self.predict_size_and_time(item, eff_crf, p) if p else (item.get('est_size_bytes', 0), 0)
        est_ratio = item.get('est_ratio', 0)
        est_kbps = est_bps // 1000 if est_bps else 0

        lines = [
            f"전체 경로: {wrapped_path}",
            f"영상 길이: {self.format_time(dur)} ({dur:.1f}초)",
            "",
            f"파일명: {vals.get('name', item.get('name', '-'))}",
            f"원본 코덱: {vals.get('orig_codec', item.get('orig_codec', '-'))}"
            f"   |   원본 해상도: {vals.get('orig_res', '-')}",
            f"원본 비트레이트: {vals.get('orig_bitrate', '-')}"
            f"   |   원본 크기: {vals.get('orig_size', self.format_size(orig_b))}",
            f"개별 화질: {vals.get('crf_sel', '-')}   (적용 CRF {eff_crf})",
            f"결과 코덱: {vals.get('result_codec', '-') or '-'}",
        ]

        if item.get('status') == "완료" and 'actual_size_b' in item:
            act_b = item['actual_size_b']
            act_bps = item.get('actual_bitrate_b', 0)
            act_kbps = act_bps // 1000 if act_bps else 0
            act_ratio = item.get('actual_ratio', 0)
            
            diff_b = act_b - est_b
            if diff_b < 0:
                diff_b_str = f"예상 대비 {self.format_size(abs(diff_b))} 더 감소 (추가 절약)"
            elif diff_b > 0:
                diff_b_str = f"예상 대비 {self.format_size(diff_b)} 증가"
            else:
                diff_b_str = "예상과 정확히 동일"

            diff_ratio = act_ratio - est_ratio
            if diff_ratio > 0.05:
                diff_r_str = f"예상 대비 {diff_ratio:+.1f}%p 더 절약"
            elif diff_ratio < -0.05:
                diff_r_str = f"예상 대비 {diff_ratio:+.1f}%p 절약 감소"
            else:
                diff_r_str = "예상과 동일"

            diff_bps = act_bps - est_bps
            diff_bps_str = f"예상 대비 {diff_bps//1000:+,d} kbps" if est_bps else ""

            lines.extend([
                "",
                "📊 [작업 완료 결과 (실제 vs 예상 비교)]",
                f" • 실제 파일 크기 : {self.format_size(act_b)} ({diff_b_str})",
                f" • 실제 압축율     : {self.format_ratio_display(act_ratio)} ({diff_r_str})",
                f" • 실제 비트레이트 : {act_kbps:,} kbps {f'({diff_bps_str})' if diff_bps_str else ''}",
                f" • 예상 파일 크기 : {self.format_size(est_b)} (예상 압축율: {self.format_ratio_display(est_ratio)})",
            ])
        else:
            lines.extend([
                "",
                "🔮 [예상 인코딩 정보]",
                f" • 예상 파일 크기 : {self.format_size(est_b)}",
                f" • 예상 압축율     : {self.format_ratio_display(est_ratio)}",
                f" • 예상 비트레이트 : {est_kbps:,} kbps",
            ])

        lines.append(f"상태: {vals.get('status', item.get('status', '-'))}")
        return "\n".join(lines)

    def _show_tree_tooltip(self, text, event, key):
        self._hide_crf_tooltip()
        try:
            tip = tk.Toplevel(self.tree)
            tip.wm_overrideredirect(True)
            tip.attributes('-topmost', True)
            tk.Label(tip, text=text, justify='left', bg='#111827', fg='#f9fafb',
                     font=("맑은 고딕", 9), padx=10, pady=8,
bd=1, relief='solid').pack()
            tip.geometry(f"+{event.x_root + 16}+{event.y_root + 14}")
            self.crf_tooltip = tip
            self.crf_tooltip_row = key
        except Exception:
            self.crf_tooltip = None
            self.crf_tooltip_row = None

    def get_preview_target(self):
        """미리보기 대상 파일: 목록에서 선택된 항목 우선, 없으면 첫 번째 파일"""
        selected = self.tree.selection()
        if selected:
            for f in self.file_list:
                if f['id'] == selected[0]:
                    return f
        return self.file_list[0] if self.file_list else None

    def get_preview_duration(self):
        """[v4.0] 미리보기 길이(초). 1~600초 자유 입력, 잘못된 값은 기본 1초."""
        raw = self.preview_duration_var.get() if hasattr(self, 'preview_duration_var') else "1"
        try:
            val_str = str(raw).replace('초', '').strip()
            if not val_str:
                self.preview_duration_var.set("1")
                return 1.0
            v = float(val_str)
        except Exception:
            self.preview_duration_var.set("1")
            return 1.0
        if not math.isfinite(v) or v <= 0:
            self.preview_duration_var.set("1")
            return 1.0
        clamped = max(1.0, min(600.0, v))
        return clamped

    def start_preview(self, target=None):
        """[v3.9] 무작위 인코딩 미리보기: 버튼·파일명 더블클릭 공용 진입점."""
        # [v4.60 fix] 미리보기 시작 전 열려 있는 셀 편집기 강제 닫기
        self._close_all_combos()
        if self.is_previewing:
            messagebox.showinfo("안내", "미리보기 작업이 이미 진행 중입니다.", parent=self.root)
            return
        if self.is_running:
            messagebox.showinfo("안내", "작업 진행 중에는 미리보기를 실행할 수 없습니다.", parent=self.root)
            return
        if not self.ffmpeg_path:
            messagebox.showwarning("안내", "FFmpeg이 설치되어 있지 않습니다.\n[도구] 메뉴에서 코덱 패키지를 설치해주세요.", parent=self.root)
            return
        if target is None:
            target = self.get_preview_target()
        if not target:
            messagebox.showinfo("안내", "미리볼 비디오를 목록에 먼저 추가해 주시기 바랍니다.", parent=self.root)
            return

        codec_check = self.get_item_codec(target)
        if "MP3" in codec_check:
            messagebox.showinfo("안내", "MP3 오디오 추출 모드는 동영상 미리보기가 제공되지 않습니다.\n(인코딩 시작 시 오디오 추출이 진행됩니다.)", parent=self.root)
            return

        duration = float(target.get('duration') or 0)
        if duration < 0.5:
            messagebox.showinfo("안내", "동영상이 너무 짧아 미리보기를 생성할 수 없습니다. (0.5초 이상 필요)", parent=self.root)
            return
        clip_len = min(self.get_preview_duration(), duration)

        eff_crf = self.get_effective_crf(target)
        try:
            snap = {
                'eff_crf': eff_crf,
                'video_args': list(self.build_video_encode_args(eff_crf, target)),
                'codec_label': self.get_item_codec(target),
                'res_label': self.combo_res.get(),
                'hw_label': self.combo_hw.get(),
                'format_label': self.combo_format.get(),
                'audio_bitrate': self.get_audio_encode_bitrate() or '192k',
            }
        except Exception as e:
            messagebox.showerror("미리보기 오류", f"인코딩 인자 생성 중 오류가 발생했습니다.\n{e}", parent=self.root)
            return

        if self.preview_popup_state:
            self._pv_close(self.preview_popup_state)

        self.is_previewing = True
        self._compare_encoding_item = target
        target['pre_compare_status'] = target.get('status', '대기 중')

        try:
            self.tree.set(target['id'], "status", f"🎬 미리보기 인코딩 중... ({clip_len:.1f}초)")
            self.tree.item(target['id'], tags=('processing',))
        except Exception:
            pass

        self.btn_preview.config(state="disabled", text="⏳ 미리보기 생성 중...")
        self.lbl_stats.config(
            text=f"미리보기 생성 중... ('{target['name']}'의 임의 장면 {clip_len:.1f}초 구간 / CRF {eff_crf})")
        threading.Thread(
            target=self._preview_thread, args=(target, clip_len, snap), daemon=True).start()

    def _preview_thread(self, target, clip_len, snap):
        try:
            max_start = max(0.0, target['duration'] - clip_len - 0.25)
            min_start = min(target['duration'] * 0.05, max_start)
            start_t = random.uniform(min_start, max_start) if max_start > min_start else 0.0

            if self.preview_temp_dir and os.path.isdir(self.preview_temp_dir):
                shutil.rmtree(self.preview_temp_dir, ignore_errors=True)
            self.preview_temp_dir = tempfile.mkdtemp(prefix="svc_preview_")
            tmp = self.preview_temp_dir

            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            ss = f"{start_t:.3f}"
            duration_arg = f"{clip_len:.3f}"

            def _is_valid_clip(filepath):
                if not os.path.exists(filepath) or os.path.getsize(filepath) < 512:
                    return False
                try:
                    chk_cmd = [self.ffprobe_path, '-v', 'error', '-select_streams', 'v:0',
                               '-show_entries', 'stream=codec_name', '-of', 'csv=p=0', filepath]
                    chk_res = subprocess.run(chk_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                             text=True, creationflags=creationflags, timeout=3)
                    return bool(chk_res.stdout.strip())
                except Exception:
                    return False

            # 1) 원본 구간 고속 추출
            orig_clip = os.path.join(tmp, "original_clip.mkv")

            motion_mp4 = target.get('motion_mp4_path') or self.extract_motion_photo_mp4(target['path'])
            is_pure_image = target.get('is_static_photo', False) or (not motion_mp4 and str(target.get('path', '')).lower().endswith(('.jpg', '.jpeg', '.jpe', '.mjpg', '.mjpeg', '.png', '.bmp')))

            if is_pure_image:
                # 순수 정지사진 / Motion Photo 비디오가 없는 JPG 파일: -loop 1로 안정적인 미리보기 동영상 클립 생성
                start_t = 0.0
                ss = "0.000"
                cmd_orig = [self.ffmpeg_path, '-y', '-loop', '1', '-t', duration_arg,
                            '-i', target['path'], '-c:v', 'libx264', '-preset', 'ultrafast',
                            '-crf', '12', '-pix_fmt', 'yuv420p', orig_clip]
                try:
                    r = subprocess.run(cmd_orig, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                       creationflags=creationflags, timeout=10)
                except subprocess.TimeoutExpired:
                    r = type('Result', (), {'returncode': -1})()
            elif motion_mp4 and os.path.exists(motion_mp4):
                # Motion Photo 내장 MP4가 존재하는 경우
                real_dur = self.check_file_real_duration(motion_mp4)
                max_seek = max(0.0, (real_dur or clip_len) - clip_len - 0.1)
                start_t = random.uniform(0.0, max_seek) if max_seek > 0.01 else 0.0
                ss = f"{start_t:.3f}"
                cmd_orig = [self.ffmpeg_path, '-y', '-ss', ss, '-i', motion_mp4,
                            '-t', duration_arg, '-c:v', 'libx264', '-preset', 'ultrafast',
                            '-crf', '12', '-pix_fmt', 'yuv420p', '-map', '0:v:0', '-map', '0:a?',
                            '-avoid_negative_ts', 'make_zero', orig_clip]
                try:
                    r = subprocess.run(cmd_orig, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                       creationflags=creationflags, timeout=12)
                except subprocess.TimeoutExpired:
                    r = type('Result', (), {'returncode': -1})()
            else:
                # 일반 동영상 파일
                cmd_orig = [self.ffmpeg_path, '-y', '-ss', ss, '-i', target['path'],
                            '-t', duration_arg, '-map', '0:v:0', '-map', '0:a?',
                            '-c', 'copy', '-avoid_negative_ts', 'make_zero', orig_clip]
                try:
                    r = subprocess.run(cmd_orig, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                       creationflags=creationflags, timeout=10)
                except subprocess.TimeoutExpired:
                    r = type('Result', (), {'returncode': -1})()

            # 원본 클립 검증 및 fallback (libx264 고속 재인코딩)
            if not _is_valid_clip(orig_clip):
                if is_pure_image:
                    cmd_orig = [self.ffmpeg_path, '-y', '-loop', '1', '-t', duration_arg,
                                '-i', target['path'], '-c:v', 'libx264', '-preset', 'ultrafast',
                                '-crf', '12', '-pix_fmt', 'yuv420p', orig_clip]
                else:
                    preview_src = motion_mp4 if (motion_mp4 and os.path.exists(motion_mp4)) else target['path']
                    cmd_orig = [self.ffmpeg_path, '-y', '-ss', ss, '-i', preview_src,
                                '-t', duration_arg, '-map', '0:v:0', '-map', '0:a?',
                                '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '12',
                                '-c:a', 'aac', '-b:a', '192k', '-avoid_negative_ts', 'make_zero',
                                orig_clip]
                try:
                    fallback = subprocess.run(
                        cmd_orig, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                        creationflags=creationflags, timeout=12)
                except subprocess.TimeoutExpired:
                    fallback = type('Result', (), {'returncode': -1})()

                if not _is_valid_clip(orig_clip):
                    raise RuntimeError("선택한 사진/이미지 파일의 미리보기 구간을 생성할 수 없습니다.")

            # 2) 압축본 미리보기 클립 생성 (오디오 무음/유무 안전 분기)
            codec_choice = snap['codec_label']
            ext = ".mkv" if ("MKV" in codec_choice or "MKV" in snap['format_label']) else ".mp4"
            comp_clip = os.path.join(tmp, f"compressed_clip{ext}")
            cmd_comp = [self.ffmpeg_path, '-y', '-i', orig_clip, '-t', duration_arg]
            cmd_comp.extend(snap['video_args'])

            acodec = target.get('audio_codec', '')
            audio_b = snap.get('audio_bitrate', '192k')
            if acodec and acodec.lower() != 'none' and audio_b not in ('음소거', None):
                if not isinstance(audio_b, str) or 'k' not in audio_b:
                    audio_b = '192k'
                cmd_comp.extend(['-c:a', 'aac', '-b:a', audio_b])
            else:
                cmd_comp.append('-an')

            cmd_comp.append(comp_clip)
            self.last_preview_cmd = " ".join(cmd_comp)

            self.preview_process = subprocess.Popen(cmd_comp, stdout=subprocess.DEVNULL,
                                                    stderr=subprocess.PIPE,
                                                    universal_newlines=True, encoding='utf-8',
                                                    errors='replace', creationflags=creationflags)
            try:
                _, err_out = self.preview_process.communicate(timeout=25)
            except subprocess.TimeoutExpired:
                self.preview_process.kill()
                self.last_preview_returncode = -1
                self.last_preview_stderr = "타임아웃 발생 (25초 초과)"
                raise RuntimeError("미리보기 인코딩 시간이 초과되었습니다. (25초 타임아웃)")

            self.last_preview_returncode = self.preview_process.returncode
            self.last_preview_stderr = "\n".join((err_out or "").strip().splitlines()[-15:]) or "성공 (오류 없음)"

            if self.preview_process.returncode != 0 or not os.path.exists(comp_clip):
                tail = "\n".join((err_out or "").strip().splitlines()[-8:])
                raise RuntimeError(f"미리보기 인코딩에 실패했습니다.\n\n[FFmpeg 로그]\n{tail}")

            # 3) 비교용 프레임 추출
            frame_orig = os.path.join(tmp, "frame_orig.png")
            frame_comp = os.path.join(tmp, "frame_comp.png")
            mid = f"{clip_len / 2:.3f}"
            for src_clip, out_png in ((orig_clip, frame_orig), (comp_clip, frame_comp)):
                subprocess.run([self.ffmpeg_path, '-y', '-i', src_clip, '-ss', mid,
                                '-vframes', '1', out_png],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=creationflags, timeout=5)
                if not os.path.exists(out_png) or os.path.getsize(out_png) == 0:
                    subprocess.run([self.ffmpeg_path, '-y', '-i', src_clip,
                                    '-vframes', '1', out_png],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   creationflags=creationflags, timeout=5)

            # 4) 통계 계산
            if target.get('duration', 0) > 0:
                orig_clip_size = target.get('orig_size_b', 0) * clip_len / target['duration']
            else:
                orig_clip_size = os.path.getsize(orig_clip) if os.path.exists(orig_clip) else 0
            comp_clip_size = os.path.getsize(comp_clip) if os.path.exists(comp_clip) else 0
            orig_info = {
                'codec': target.get('orig_codec') or 'UNKNOWN',
                'bitrate': target.get('orig_bitrate') or 'N/A',
            }
            comp_info = self.analyze_output_file(comp_clip)

            est_full_size = 0
            if orig_clip_size > 0 and comp_clip_size > 0:
                ratio = comp_clip_size / orig_clip_size
                est_full_size = target['orig_size_b'] * ratio

            result = {
                'target': target, 'start_t': start_t, 'clip_len': clip_len,
                'orig_clip': orig_clip, 'comp_clip': comp_clip,
                'frame_orig': frame_orig, 'frame_comp': frame_comp,
                'orig_clip_size': orig_clip_size, 'comp_clip_size': comp_clip_size,
                'orig_info': orig_info, 'comp_info': comp_info,
                'est_full_size': est_full_size,
                'eff_crf': snap['eff_crf'], 'codec_label': snap['codec_label'],
                'res_label': snap['res_label'], 'hw_label': snap['hw_label'],
            }
            self.root.after(0, self.show_preview_window, result)
        except Exception as e:
            err_msg = str(e)
            def _show_friendly_preview_err(msg_text):
                messagebox.showinfo(
                    "💡 미리보기 안내",
                    f"선택하신 사진/미디어 파일은 1초 숏클립 미리보기를 지원하지 않습니다.\n\n"
                    f"사유: {msg_text[:120]}\n\n"
                    f"📌 하단의 [작업 시작] 버튼을 누르시면 전체 인코딩/병합 작업이 정상 진행됩니다.",
                    parent=self.root
                )
            self.root.after(0, _show_friendly_preview_err, err_msg)
        finally:
            self.root.after(0, self._preview_done)




    def _on_tree_motion(self, event):
        """[v3.9] 개별 화질 컬럼은 화질 상세 툴팁, 그 외 컬럼은 파일 전체 정보 툴팁."""
        try:
            region = self.tree.identify('region', event.x, event.y)
            if region != 'cell':
                self._hide_crf_tooltip()
                return
            column = self.tree.identify_column(event.x)
            row_id = self.tree.identify_row(event.y)
        except Exception:
            return
        if not row_id:
            self._hide_crf_tooltip()
            return
        if column == '#7':
            kind = 'crf'
        elif column == '#9':
            kind = 'size'
        else:
            kind = 'info'
            
        key = (row_id, kind)
        if self.crf_tooltip is not None and self.crf_tooltip_row == key:
            return
        item = self._get_item_by_id(row_id)
        if not item:
            self._hide_crf_tooltip()
            return
        try:
            if kind == 'crf':
                text = self._build_crf_tooltip_text(item)
            elif kind == 'size':
                text = item.get('tooltip_size_info', '')
                if not text:
                    return
            else:
                text = self._build_item_info_tooltip(item)
        except Exception:
            return
        self._show_tree_tooltip(text, event, key)

    def _hide_crf_tooltip(self):
        if self.crf_tooltip is not None:
            try:
                self.crf_tooltip.destroy()
            except Exception:
                pass
            self.crf_tooltip = None
            self.crf_tooltip_row = None



    def get_color_gauge(self, ratio):
        """압축 효율에 따른 막대 그래프(이모지) 문자열 반환"""
        total = 10
        if ratio < 0:
            return "🟥" * total  # 원본보다 증가시 모두 빨간색
        
        blocks = min(total, max(1, int(ratio * total)))
        empty = total - blocks
        
        if ratio <= 0.05:
            char = "🟧"
        elif ratio <= 0.3:
            char = "🟨"
        else:
            char = "🟩"
            
        return (char * blocks) + ("⬜" * empty)

    def update_summary_panel(self, orig_size, est_size, rem_time, total_duration=0):
        count = len(self.file_list)
        if total_duration == 0 and count > 0:
            total_duration = sum(float(item.get('duration', 0) or 0) for item in self.file_list)

        if count == 0:
            for key, val_str in [("count", "0개"), ("orig", "0 MB"), ("duration", "0초"),
                                 ("est", "0 MB"), ("ratio", "0%"), ("time", "0초")]:
                if key in self.summary_labels:
                    lbl, title = self.summary_labels[key]
                    lbl.config(text=f"{title}: {val_str}")
            return

        ratio = ((orig_size - est_size) / orig_size * 100) if orig_size > 0 else 0

        val_dict = {
            "count": f"{count:,}개",
            "orig": self.format_size(orig_size),
            "duration": f"약 {self.format_time(total_duration)}",
            "est": self.format_size(est_size),
            "ratio": f"약 {self.format_ratio_display(ratio)} 절약",
            "time": f"약 {self.format_time(rem_time)}"
        }

        for key, val_str in val_dict.items():
            if key in self.summary_labels:
                lbl, title = self.summary_labels[key]
                lbl.config(text=f"{title}: {val_str}")

    def process_added_files(self, files, src_root=None):
        if not files:
            return
        # 매번 끌어오는 파일들을 파일명 기준 가나다/자연어 정렬 후 추가
        sorted_files = sorted(list(dict.fromkeys(files)), key=self._natural_sort_key)
    def _auto_clean_old_versions(self):
        """Automatically moves any older version files (smart_video_compressor_v*.py/pyw/spec/exe) to old/ and old/dist/."""
        try:
            root_dir = Path(__file__).resolve().parent if '__file__' in globals() else Path.cwd()
            current_ver_stem = "smart_video_compressor_v4.67g"
            old_dir = root_dir / "old"
            old_dist_dir = old_dir / "dist"
            old_dir.mkdir(parents=True, exist_ok=True)
            old_dist_dir.mkdir(parents=True, exist_ok=True)

            for item in list(root_dir.glob("smart_video_compressor_v*")):
                if item.name.startswith(current_ver_stem):
                    continue
                if item.is_file():
                    ext = item.suffix.lower()
                    if ext == ".exe":
                        dst = old_dist_dir / item.name
                        if dst.exists():
                            try:
                                dst.unlink()
                            except Exception:
                                pass
                        try:
                            shutil.move(str(item), str(dst))
                            print(f"[AutoClean] Moved old EXE: {item.name} -> old/dist/")
                        except Exception as ex_m:
                            print(f"[AutoClean EXE Exception] {ex_m}")
                    elif ext in (".py", ".pyw", ".spec"):
                        dst = old_dir / item.name
                        if dst.exists():
                            try:
                                dst.unlink()
                            except Exception:
                                pass
                        try:
                            shutil.move(str(item), str(dst))
                            print(f"[AutoClean] Moved old source: {item.name} -> old/")
                        except Exception as ex_m:
                            print(f"[AutoClean Source Exception] {ex_m}")
        except Exception as e:
            print(f"[AutoClean Global Exception] {e}")

    def read_subtitle_content_utf8(self, file_path):
        """Reads any subtitle file (SRT, SMI, ASS, VTT) with automatic encoding detection (UTF-8, UTF-8-SIG, CP949, EUC-KR, UTF-16)."""
        path = Path(file_path)
        if not path.exists():
            return ""
        raw = path.read_bytes()
        for enc in ('utf-8-sig', 'cp949', 'euc-kr', 'utf-16', 'utf-8', 'latin1'):
            try:
                return raw.decode(enc)
            except Exception:
                continue
        return raw.decode('utf-8', errors='replace')

    def parse_smi_content(self, content):
        """Parses SMI (SAMI) subtitle content into list of (start_sec, end_sec, text)."""
        sync_blocks = re.findall(r'<SYNC\s+Start=(\d+)[^>]*>(.*?)(?=<SYNC|\Z)', content, re.IGNORECASE | re.DOTALL)
        entries = []
        for i, (start_ms, text_block) in enumerate(sync_blocks):
            st_sec = int(start_ms) / 1000.0
            if i + 1 < len(sync_blocks):
                et_sec = int(sync_blocks[i+1][0]) / 1000.0
            else:
                et_sec = st_sec + 4.0
            if et_sec <= st_sec:
                et_sec = st_sec + 2.0

            text = re.sub(r'<P[^>]*>', '', text_block, flags=re.IGNORECASE)
            text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
            text = re.sub(r'<[^>]+>', '', text)
            text = text.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            clean_text = '\n'.join(lines)
            if clean_text:
                entries.append((st_sec, et_sec, clean_text))
        return entries

    def parse_srt_time(self, t_str):
        """Converts '00:01:23,456' or '00:01:23.456' to float seconds."""
        t_str = t_str.strip().replace('.', ',')
        try:
            parts = t_str.split(':')
            h = int(parts[0])
            m = int(parts[1])
            s_parts = parts[2].split(',')
            s = int(s_parts[0])
            ms = int(s_parts[1]) if len(s_parts) > 1 else 0
            return h * 3600.0 + m * 60.0 + s + ms / 1000.0
        except Exception:
            return 0.0

    def format_srt_time(self, seconds):
        """Converts float seconds to '00:01:23,456'."""
        if seconds < 0:
            seconds = 0.0
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int(round((seconds - int(seconds)) * 1000))
        if ms >= 1000:
            s += 1
            ms = 0
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def extract_or_read_srt(self, item, temp_dir, idx):
        """Extracts embedded subtitle or reads external subtitle file (.srt, .smi, .ass, .vtt), returning list of (start_sec, end_sec, text)."""
        sub_path = None
        ext_file = item.get('ext_sub_file')
        if ext_file and os.path.exists(ext_file):
            sub_path = ext_file
        elif item.get('has_embedded_sub') and getattr(self, 'ffmpeg_path', None):
            out_srt = os.path.join(temp_dir, f"extracted_{idx}.srt")
            cmd = [self.ffmpeg_path, '-y', '-hide_banner', '-loglevel', 'error',
                   '-i', item['path'], '-map', '0:s:0', out_srt]
            try:
                creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               creationflags=creationflags, timeout=30)
                if os.path.exists(out_srt) and os.path.getsize(out_srt) > 0:
                    sub_path = out_srt
            except Exception:
                pass

        if not sub_path or not os.path.exists(sub_path):
            return []

        content = self.read_subtitle_content_utf8(sub_path)
        if not content:
            return []

        # Check SMI format
        if '<SAMI>' in content.upper() or '<SYNC' in content.upper():
            return self.parse_smi_content(content)

        entries = []
        blocks = re.split(r'\n\s*\n', content.strip())
        for b in blocks:
            lines = [l.strip() for l in b.splitlines() if l.strip()]
            if not lines:
                continue
            time_line_idx = -1
            for i, l in enumerate(lines):
                if '-->' in l:
                    time_line_idx = i
                    break
            if time_line_idx == -1:
                continue
            t_line = lines[time_line_idx]
            parts = t_line.split('-->')
            if len(parts) != 2:
                continue
            t_start = self.parse_srt_time(parts[0])
            t_end = self.parse_srt_time(parts[1])
            text_lines = lines[time_line_idx + 1:]
            text = '\n'.join(text_lines)
            if text:
                entries.append((t_start, t_end, text))
        return entries

    def _analyze_files_thread(self, files, src_root=None):
        total_count = len(files)
        analyze_start = time.time()
        # [v4.631c] 분석 진단용 통계 변수
        self._analyze_stats = {
            'total_input': total_count,
            'processed': 0,
            'static_photo': 0,
            'motion_jpeg': 0,
            'general_video': 0,
            'skipped_duplicate': 0,
            'skipped_photo_filter': 0,
            'ffprobe_error': 0,
            'timeout_error': 0,
            'path_not_found': 0,
            'already_in_list': 0,
            'no_video_stream': 0,
            'exceptions': [],
            'sample_ffprobe_results': [],  # 처음 3개 파일의 ffprobe 결과 샘플
            'skipped_photo_details': [],   # 정지사진 제외 판별 상세 정보 샘플
            'photo_option_at_start': self.photo_option_var.get() if hasattr(self, 'photo_option_var') else 'N/A',
        }
        last_ui_update_time = 0
        self.root.after(0, lambda: self.lbl_stats.config(text=f"🔍 메타데이터 분석 중... (0/{total_count}개, 0% | 🎥 추가: 0개, 🖼️ 정지사진 제외: 0개)"))
        for file_idx, filepath_raw in enumerate(files, 1):
            try:
                safe_path = Path(filepath_raw).resolve()
                if not safe_path.exists():
                    print(f"경로 접근 실패: {safe_path}")
                    self._analyze_stats['path_not_found'] += 1
                    continue
                filepath = str(safe_path)

                if any(item['path'] == filepath for item in self.file_list):
                    self._analyze_stats['already_in_list'] += 1
                    # [v4.657 FIX] 이미 대기열에 있더라도 모션 JPEG 모드에서 오탐 정지사진(무음+내장MP4없음)이면 자동 정화 삭제!
                    p_opt_chk = self.photo_option_var.get() if hasattr(self, 'photo_option_var') else ''
                    if "모션 JPEG" in p_opt_chk:
                        for ex_item in list(self.file_list):
                            if ex_item['path'] == filepath:
                                is_ex_static = ex_item.get('is_static_photo', False)
                                ex_m_mp4 = ex_item.get('motion_mp4_path', '')
                                ex_codec = str(ex_item.get('orig_codec', ''))
                                if is_ex_static or '헤더감지' in ex_codec or (not ex_m_mp4 and not self.check_file_has_audio(filepath, ex_item)):
                                    self.file_list = [f for f in self.file_list if f['path'] != filepath]
                                    self.root.after(0, lambda iid=ex_item['id']: self.tree.delete(iid) if self.tree.exists(iid) else None)
                                    self._analyze_stats['skipped_photo_filter'] += 1
                    continue

                # [v4.64f] Motion Photo (.jpg) 매립 MP4 동영상 바이너리 파이로드 자동 추출
                # XMP MicroVideoOffset 태그 우선 파싱 → ftyp/moov 바이너리 탐색 순으로 추출
                motion_mp4 = self.extract_motion_photo_mp4(filepath)
                probe_target = motion_mp4 if motion_mp4 else filepath

                creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                cmd = [self.ffprobe_path, '-v', 'error',
                       '-show_entries', 'stream=index,codec_type,width,height,duration,codec_name,bit_rate,r_frame_rate',
                       '-show_entries', 'format=size,bit_rate,duration',
                       '-of', 'json', probe_target]

                try:
                    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                            text=True, encoding='utf-8', errors='replace',
                                            creationflags=creationflags, timeout=5)
                except subprocess.TimeoutExpired:
                    self._analyze_stats['timeout_error'] += 1
                    self._analyze_stats['exceptions'].append(f"ffprobe 타임아웃(5초 초과 스킵): {safe_path.name}")
                    continue
                except Exception as ex:
                    self._analyze_stats['ffprobe_error'] += 1
                    self._analyze_stats['exceptions'].append(f"ffprobe 실행 오류: {safe_path.name} -> {ex}")
                    continue

                if result.returncode != 0:
                    self._analyze_stats['ffprobe_error'] += 1
                    self._analyze_stats['exceptions'].append(f"ffprobe rc={result.returncode}: {safe_path.name} -> {result.stderr[:200]}")
                    continue

                info = json.loads(result.stdout)

                streams = info.get('streams', [{}])
                v_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)
                suffix = safe_path.suffix.lower()
                is_jpeg_ext = suffix in ('.jpg', '.jpeg', '.jpe', '.mjpg', '.mjpeg', '.mjp')

                if v_stream is None:
                    # [v4.655 FIX] ffprobe가 비디오 스트림을 찾지 못한 경우 = 정지사진 가능성 높음
                    # motion_mp4가 없으면 100% 정지사진으로 처리 (헤더감지 오탐 차단)
                    if is_jpeg_ext and not motion_mp4:
                        # 비디오 스트림도 없고 내장 MP4도 없는 JPG/JPEG는 정지사진으로 즉시 처리
                        p_opt_chk = self.photo_option_var.get() if hasattr(self, 'photo_option_var') else ''
                        if "모션 JPEG" in p_opt_chk:
                            if not hasattr(self, '_skipped_photo_count'):
                                self._skipped_photo_count = 0
                            self._skipped_photo_count += 1
                            self._analyze_stats['skipped_photo_filter'] += 1
                            if len(self._analyze_stats.get('skipped_photo_details', [])) < 20:
                                self._analyze_stats['skipped_photo_details'].append({
                                    'name': safe_path.name,
                                    'dur': 0.0,
                                    'has_audio': False,
                                    'res': 'N/A',
                                    'reason': 'FILTERED_NO_VIDEO_STREAM (비디오스트림&내장MP4 없음)'
                                })
                        else:
                            self._analyze_stats['static_photo'] += 1
                        continue
                    elif is_jpeg_ext and motion_mp4:
                        # motion_mp4가 있으면 그것의 스트림을 읽어야 하므로 더미 v_stream 허용
                        v_stream = {'codec_name': 'mjpeg', 'width': 1920, 'height': 1080, 'duration': 3.0}
                    else:
                        self._analyze_stats['no_video_stream'] += 1
                        continue
                # [v3.0] 오디오 스트림 정보 ('원본 유지' 오디오 및 예측 계산용)
                a_stream = next((s for s in streams if s.get('codec_type') == 'audio'), {})
                audio_codec = (a_stream.get('codec_name') or '').lower()
                try:
                    audio_bps_src = int(a_stream.get('bit_rate') or 0)
                except Exception:
                    audio_bps_src = 0
                fmt = info.get('format', {})

                # [v4.67b] 자막 스트림(내장) 및 동종 경로 외장 자막 파일(.srt, .ass, .vtt, .smi) 탐지
                sub_streams = [s for s in streams if s.get('codec_type') == 'subtitle']
                has_embedded_sub = len(sub_streams) > 0
                sub_codecs = [s.get('codec_name', '').lower() for s in sub_streams]

                ext_sub_file = ''
                stem = safe_path.stem
                parent_dir = safe_path.parent
                for ext_cand in ('.srt', '.ass', '.vtt', '.smi', '.sub', '.ko.srt', '.en.srt'):
                    cand = parent_dir / f"{stem}{ext_cand}"
                    if cand.exists():
                        ext_sub_file = str(cand)
                        break

                has_subtitle = has_embedded_sub or bool(ext_sub_file)
                subtitle_info = ""
                if has_embedded_sub and ext_sub_file:
                    subtitle_info = f"내장 {len(sub_streams)}개({','.join(sub_codecs)}) + 외장 자막({Path(ext_sub_file).name})"
                elif has_embedded_sub:
                    subtitle_info = f"내장 자막 {len(sub_streams)}개({','.join(sub_codecs)})"
                elif ext_sub_file:
                    subtitle_info = f"외장 자막 ({Path(ext_sub_file).name})"

                # [v4.64f FIX] 갤럭시 모션포토 핵심 버그 수정:
                # ffprobe가 JPG 원본을 image2(단일프레임)로 읽으면 오디오 스트림이 보이지 않음.
                # motion_mp4가 추출된 경우 → 반드시 실제 MP4 파일에서 오디오 재확인
                # motion_mp4가 없더라도 JPG가 image2 포맷(0.04초)이고 파일크기가 크면 → 재추출 재시도
                if not audio_codec and motion_mp4 and os.path.exists(motion_mp4):
                    # 추출된 MP4에서 오디오 스트림 직접 확인
                    has_audio = self.check_file_has_audio(motion_mp4)
                    if has_audio:
                        # MP4에서 오디오 코덱 정보 추가 획득
                        try:
                            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                            _cmd = [self.ffprobe_path, '-v', 'error',
                                    '-show_entries', 'stream=codec_name,bit_rate',
                                    '-select_streams', 'a:0',
                                    '-of', 'json', motion_mp4]
                            _r = subprocess.run(_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                                text=True, encoding='utf-8', errors='replace',
                                                creationflags=creationflags, timeout=4)
                            _info = json.loads(_r.stdout or '{}')
                            _astreams = _info.get('streams', [])
                            if _astreams:
                                audio_codec = (_astreams[0].get('codec_name') or 'aac').lower()
                                try:
                                    audio_bps_src = int(_astreams[0].get('bit_rate') or 0)
                                except Exception:
                                    audio_bps_src = 0
                        except Exception:
                            audio_codec = 'aac'  # 기본값
                else:
                    has_audio = bool(audio_codec and audio_codec != 'none')

                v_dur = float(v_stream.get('duration') or 0)
                fmt_dur = float(fmt.get('duration') or 0)
                a_dur = float(a_stream.get('duration') or 0)
                raw_dur = max(v_dur, fmt_dur, a_dur)

                # [v4.64f FIX] image2 포맷(0.04초)이고 크기가 크면 → 갤럭시 모션포토 재추출 시도
                _is_image2 = fmt.get('format_name', '') == 'image2'
                _orig_sz = int(fmt.get('size', 0))
                if _is_image2 and not motion_mp4 and is_jpeg_ext and _orig_sz > 500000:
                    # XMP 기반 재추출 시도
                    motion_mp4 = self.extract_motion_photo_mp4(filepath)
                    if motion_mp4 and os.path.exists(motion_mp4):
                        # 재추출 성공: MP4에서 오디오/재생시간 재확인
                        has_audio = self.check_file_has_audio(motion_mp4)
                        if has_audio:
                            audio_codec = 'aac'
                        # MP4 재생시간 재측정
                        try:
                            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                            _cmd2 = [self.ffprobe_path, '-v', 'error',
                                     '-show_entries', 'format=duration',
                                     '-of', 'json', motion_mp4]
                            _r2 = subprocess.run(_cmd2, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                                 text=True, encoding='utf-8', errors='replace',
                                                 creationflags=creationflags, timeout=4)
                            _info2 = json.loads(_r2.stdout or '{}')
                            _new_dur = float(_info2.get('format', {}).get('duration') or 0)
                            if _new_dur > 0:
                                raw_dur = _new_dur
                        except Exception:
                            pass

                width = v_stream.get('width', 0)
                height = v_stream.get('height', 0)
                size_bytes = int(fmt.get('size', 0))

                suffix = safe_path.suffix.lower()
                is_jpeg_ext = suffix in ('.jpg', '.jpeg', '.jpe', '.mjpg', '.mjpeg', '.mjp')

                # [v4.657 FIX] 상태 판별 사유 코드 (Reason Code) 산출
                if is_jpeg_ext and not motion_mp4 and not has_audio:
                    reason_code = "FILTERED_BY_NO_AUDIO_JPEG (내장MP4없음+음성없음 정지사진 원천차단)"
                elif motion_mp4:
                    reason_code = "ADDED_VALID_MOTION_PHOTO (유효 MP4 헤더 검증 성공 모션포토)"
                elif is_jpeg_ext and has_audio:
                    reason_code = "ADDED_VALID_AUDIO_MJPEG (음성 트랙 포함 MJPEG 동영상)"
                elif is_jpeg_ext:
                    reason_code = "ADDED_STATIC_PHOTO_SLIDE (슬라이드 생성 모드 정지사진)"
                else:
                    reason_code = "ADDED_GENERAL_VIDEO (일반 비디오 파일)"

                # [v4.631c] ffprobe 샘플 결과 수집 (처음 5개)
                if len(self._analyze_stats['sample_ffprobe_results']) < 5:
                    self._analyze_stats['sample_ffprobe_results'].append({
                        'name': safe_path.name,
                        'reason_code': reason_code,
                        'has_audio': has_audio,
                        'raw_dur': raw_dur,
                        'v_dur': v_dur,
                        'a_dur': a_dur,
                        'fmt_dur': fmt_dur,
                        'is_jpeg_ext': is_jpeg_ext,
                        'is_static_photo': (is_jpeg_ext and not has_audio and not motion_mp4),
                        'codec_name': v_stream.get('codec_name', 'unknown'),
                        'audio_codec': audio_codec or 'none',
                        'width': width,
                        'height': height,
                    })

                # [v4.631j] 헤더 4KB 바이너리 정밀 검사 (FourCC MJPG/mjpeg/dmb1/jpeg 및 복수 SOI \xff\xd8 마커 검사)
                is_mjpeg_hdr = self.check_mjpeg_binary_header(filepath)

                if motion_mp4:
                    # [v4.654 FIX] Samsung/Google Motion Photo (내장 MP4 동영상 바이너리 추출 성공)
                    is_static_photo = False
                    self._analyze_stats['motion_jpeg'] += 1
                    duration = raw_dur if raw_dur > 0.5 else 3.0
                    codec_name = f"Motion Photo ({v_stream.get('codec_name', 'MP4').upper()})"
                elif is_jpeg_ext and has_audio:
                    # [v4.654 FIX] 오디오 스트림이 존재하는 진짜 음성 포함 MJPEG 비디오
                    is_static_photo = False
                    self._analyze_stats['motion_jpeg'] += 1
                    duration = raw_dur if raw_dur > 0.5 else 3.0
                    codec_name = "MJPEG (음성포함)"
                elif is_jpeg_ext:
                    # [v4.654 FIX] 내장 MP4도 없고 오디오도 없는 모든 JPG/JPEG 미디어는 100% 정지 사진으로 원천 분류!
                    is_static_photo = True
                    self._analyze_stats['static_photo'] += 1
                    p_opt = getattr(self, 'photo_option_var', None).get() if hasattr(self, 'photo_option_var') else "3초"
                    if "5초" in p_opt:
                        duration = 5.0
                    elif "1초" in p_opt:
                        duration = 1.0
                    else:
                        duration = 3.0
                    codec_name = "JPEG (정지사진)"
                else:
                    is_static_photo = False
                    self._analyze_stats['general_video'] += 1
                    duration = raw_dur
                    codec_name = v_stream.get('codec_name', 'unknown').upper()

                bitrate = 0
                try:
                    bitrate = int(v_stream.get('bit_rate') or fmt.get('bit_rate') or 0)
                    bitrate_str = f"{bitrate // 1000:,} kbps" if bitrate > 0 else "N/A"
                except Exception:
                    bitrate_str = "N/A"

                # [v2.4] 화질 예측용 프레임레이트 파싱 (예: "30000/1001")
                fps = 30.0
                try:
                    fr = v_stream.get('r_frame_rate', '') or ''
                    if '/' in fr:
                        num, den = fr.split('/')
                        if float(den) > 0:
                            fps = float(num) / float(den)
                    elif fr:
                        fps = float(fr)
                except Exception:
                    fps = 30.0
                if not (1 <= fps <= 240):
                    fps = 30.0

                res_str = f"{width}x{height}"

                # [v3.0] 폴더 추가 시: 원본 루트 기준 상대 경로 기억 (저장 폴더 미러링용)
                rel_dir = ''
                disp_name = safe_path.name
                if src_root:
                    try:
                        src_root_resolved = Path(src_root).resolve()
                        rel = safe_path.resolve().relative_to(src_root_resolved)
                        rel_dir = str(rel.parent) if str(rel.parent) != '.' else ''
                        r_name = src_root_resolved.name or src_root_resolved.drive.rstrip(':\\') or "root"
                        disp_name = f"{r_name}/{rel}".replace('\\', '/')
                    except ValueError:
                        src_root = None

                # [v4.67b] 자막 보유 파일에 대기열 표식 (💬 [자막]) 추가
                if has_subtitle:
                    disp_name = f"💬 [자막] {disp_name}"

                file_info = {
                    'id': f"file_{uuid.uuid4().hex}",
                    'path': filepath,
                    'motion_mp4_path': motion_mp4 if motion_mp4 else '',
                    'name': safe_path.name,
                    'disp_name': disp_name,
                    'src_root': str(src_root) if src_root else '',
                    'rel_dir': rel_dir,
                    'audio_codec': audio_codec,
                    'audio_bps_src': audio_bps_src,
                    'duration': duration,
                    'is_static_photo': is_static_photo,
                    'has_subtitle': has_subtitle,
                    'has_embedded_sub': has_embedded_sub,
                    'ext_sub_file': ext_sub_file,
                    'subtitle_info': subtitle_info,
                    'orig_codec': codec_name,
                    'orig_res': res_str,
                    'orig_bitrate': bitrate_str,
                    'orig_width': width,
                    'orig_height': height,
                    'orig_size_b': size_bytes,
                    'orig_size': f"{size_bytes / (1024**2):.1f} MB",
                    'orig_bitrate_b': bitrate,   # [v2.4] 수치 비트레이트(bps, 0이면 크기/길이로 추정)
                    'orig_fps': fps,             # [v2.4] 프레임레이트
                    'crf_mode': self.auto_profile_to_mode(self.get_auto_quality_profile()),  # [v3.3] 자동화질 기준
                    'status': "대기 중"
                }

                # [v4.656 FIX] '모션 JPEG만 작업' 선택 시 제외 대상 필터링 (is_static_photo OR 내장MP4없음+오디오없는 JPEG 전체)
                p_opt_cur = self.photo_option_var.get() if hasattr(self, 'photo_option_var') else ''
                _is_motion_jpeg_mode = "모션 JPEG" in p_opt_cur

                # 제외 조건: 정지사진으로 판명되었거나, JPEG 확장자이면서 내장 MP4도 없고 오디오도 없는 파일
                _should_skip = is_static_photo or (is_jpeg_ext and not motion_mp4 and not has_audio)

                if _is_motion_jpeg_mode and _should_skip:
                    if not hasattr(self, '_skipped_photo_count'):
                        self._skipped_photo_count = 0
                    self._skipped_photo_count += 1
                    self._analyze_stats['skipped_photo_filter'] += 1
                    if len(self._analyze_stats.get('skipped_photo_details', [])) < 20:
                        self._analyze_stats['skipped_photo_details'].append({
                            'name': safe_path.name,
                            'dur': raw_dur,
                            'has_audio': has_audio,
                            'res': f"{width}x{height}"
                        })
                    continue

                self._analyze_stats['processed'] += 1
                self.file_list.append(file_info)
                self.root.after(0, self._add_to_tree, file_info)

                # [v4.631] 정지사진 옵션 활성화: JPEG 이미지가 추가되면 콤보 활성화
                if is_jpeg_ext:
                    self.root.after(0, lambda: self.combo_photo_option.config(state='readonly'))

            except Exception as e:
                print(f"분석 오류 ({filepath_raw}): {e}")
                if hasattr(self, '_analyze_stats'):
                    self._analyze_stats['exceptions'].append(f"{Path(filepath_raw).name}: {str(e)[:150]}")

            finally:
                # [v4.631h FIX] continue나 exception과 무관하게 항상 진행률 및 카운터를 갱신한다!
                now_t = time.time()
                if file_idx % 5 == 0 or file_idx == total_count or (now_t - last_ui_update_time) >= 0.15:
                    last_ui_update_time = now_t
                    elapsed = now_t - analyze_start
                    pct = (file_idx / total_count) * 100
                    if file_idx > 1 and elapsed > 0:
                        eta = (elapsed / file_idx) * (total_count - file_idx)
                        eta_str = f", 남은시간: {int(eta//60)}분 {int(eta%60)}초" if eta >= 60 else f", 남은시간: {int(eta)}초"
                    else:
                        eta_str = ""
                    
                    added_c = self._analyze_stats['processed']
                    skipped_c = self._analyze_stats['skipped_photo_filter']
                    status_str = (f"🔍 메타데이터 분석 중... ({file_idx}/{total_count}개, {pct:.0f}% | "
                                  f"🎥 추가: {added_c}개, 🖼️ 정지사진 제외: {skipped_c}개{eta_str})")
                    self.root.after(0, lambda s=status_str: self.lbl_stats.config(text=s))

        # [v4.631g] 분석 완료 결과 종합 안내
        skipped = getattr(self, '_skipped_photo_count', 0)
        self._skipped_photo_count = 0
        added_final = len(self.file_list)

        self.root.after(0, self.auto_apply_recommended_crf)
        if getattr(self, 'skip_duplicate_files', None) and self.skip_duplicate_files.get():
            self.root.after(0, lambda: self.filter_duplicates_in_queue(show_msg=False))

        final_msg = f"총 {added_final}개 파일 준비 완료 (🖼️ 정지사진 {skipped}개 자동 제외됨)" if skipped > 0 else f"총 {added_final}개 파일 준비 완료"
        self.root.after(0, lambda: self.lbl_stats.config(text=final_msg))

        if skipped > 0:
            info_popup_msg = (
                f"🔍 메타데이터 분석 및 정지사진 필터링 완료\n\n"
                f"• 🎥 대기열 목록 추가 (작업 대상): {added_final}개\n"
                f"• 🖼️ 정지사진 자동 제외 ('모션 JPEG만' 옵션): {skipped}개\n"
                f"  └ (제외 기준: 음성이 없고 재생 시간이 0.5초 이하인 단일 정지 사진)\n\n"
                f"💡 어떤 파일이 정지사진으로 판별되어 제외되었는지 구체적 데이터(재생시간, 음성 유무, 해상도 등)는 '디버깅 리포트'(Ctrl+D)에서 확인하실 수 있습니다."
            )
        self.build_version = "v4.65o (Build 20260728 - Filename UI & Auto Delete)"

    @staticmethod
    def _parse_xmp_micro_video_offset(file_path):
        """[v4.64f NEW] 갤럭시/픽셀 모션포토 JPEG의 XMP 메타데이터에서
        MicroVideoOffset(= 파일 끝에서 MP4까지의 바이트 오프셋) 값을 추출한다.
        반환: int(offset) 또는 None"""
        try:
            with open(file_path, 'rb') as f:
                # JPEG APP 마커 순서대로 스캔, 최대 1MB까지
                header = f.read(min(1048576, os.path.getsize(file_path)))

            # XMP 패킷 감지 (APP1 내 'http://ns.adobe.com/xap/1.0/' 헤더)
            xmp_start = header.find(b'http://ns.adobe.com/xap')
            if xmp_start == -1:
                # Extended XMP도 확인
                xmp_start = header.find(b'http://ns.adobe.com/xmp')
            if xmp_start == -1:
                return None

            xmp_end = header.find(b'</x:xmpmeta>', xmp_start)
            if xmp_end == -1:
                xmp_end = xmp_start + 32768
            xmp_data = header[xmp_start:xmp_end + 32].decode('utf-8', errors='replace')

            # MicroVideoOffset / MicroVideoLength 태그 파싱 (갤럭시/Pixel 공통)
            import re
            for pattern in [
                r'Camera:MicroVideoOffset\s*=\s*["\']?(\d+)',
                r'GCamera:MicroVideoOffset\s*=\s*["\']?(\d+)',
                r'MicroVideoOffset\s*=\s*["\']?(\d+)',
                r'<Camera:MicroVideoOffset>(\d+)</Camera:MicroVideoOffset>',
                r'<GCamera:MicroVideoOffset>(\d+)</GCamera:MicroVideoOffset>',
                r'TrailerOffset\s*=\s*["\']?(\d+)',
                r'Samsung:MicroVideoOffset\s*=\s*["\']?(\d+)',
            ]:
                m = re.search(pattern, xmp_data)
                if m:
                    return int(m.group(1))
        except Exception:
            pass
        return None

    @staticmethod
    def extract_motion_photo_mp4(file_path):
        """[v4.64f FIX] 삼성/픽셀/샤오미 등 모든 기종 Motion Photo 내장 MP4 완전 추출.
        우선순위:
          1. XMP MicroVideoOffset 태그 → 정확한 오프셋으로 추출 (갤럭시 표준)
          2. ftyp/moov 박스 바이너리 탐색 (기타 기종 호환)
        """
        if not file_path or not str(file_path).lower().endswith(('.jpg', '.jpeg', '.jpe')):
            return None

        try:
            file_size = os.path.getsize(file_path)
            if file_size < 8192:
                return None

            stem = Path(file_path).stem

            # ── 1단계: XMP MicroVideoOffset 파싱 (갤럭시 표준 방식) ──
            micro_offset = None
            try:
                with open(file_path, 'rb') as f:
                    header_data = f.read(min(1048576, file_size))

                xmp_start = header_data.find(b'http://ns.adobe.com/xap')
                if xmp_start == -1:
                    xmp_start = header_data.find(b'http://ns.adobe.com/xmp')
                if xmp_start != -1:
                    xmp_end = header_data.find(b'</x:xmpmeta>', xmp_start)
                    xmp_slice = header_data[xmp_start:xmp_end + 32 if xmp_end != -1 else xmp_start + 32768]
                    xmp_text = xmp_slice.decode('utf-8', errors='replace')

                    import re
                    for pattern in [
                        r'Camera:MicroVideoOffset\s*=\s*["\']?(\d+)',
                        r'GCamera:MicroVideoOffset\s*=\s*["\']?(\d+)',
                        r'MicroVideoOffset\s*=\s*["\']?(\d+)',
                        r'<Camera:MicroVideoOffset>(\d+)</Camera:MicroVideoOffset>',
                        r'<GCamera:MicroVideoOffset>(\d+)</GCamera:MicroVideoOffset>',
                        r'TrailerOffset\s*=\s*["\']?(\d+)',
                        r'Samsung:MicroVideoOffset\s*=\s*["\']?(\d+)',
                    ]:
                        m = re.search(pattern, xmp_text)
                        if m:
                            micro_offset = int(m.group(1))
                            break
            except Exception:
                pass

            if micro_offset is not None:
                # MicroVideoOffset = 파일 끝에서부터의 바이트 수
                start_offset = file_size - micro_offset
                if 0 < start_offset < file_size:
                    tmp_mp4 = os.path.join(
                        tempfile.gettempdir(),
                        f"motion_photo_{stem}_{start_offset}.mp4"
                    )
                    with open(file_path, 'rb') as f:
                        f.seek(start_offset)
                        video_data = f.read()
                    if len(video_data) > 4096:
                        if not os.path.exists(tmp_mp4) or os.path.getsize(tmp_mp4) != len(video_data):
                            with open(tmp_mp4, 'wb') as vf:
                                vf.write(video_data)
                        return tmp_mp4

            # ── 2단계: 파일 전체에서 ftyp/moov 박스 바이너리 탐색 ──
            with open(file_path, 'rb') as f:
                data = f.read()

            data_len = len(data)

            # 2a: ftyp 박스 탐색
            search_start = 0
            while True:
                pos = data.find(b'ftyp', search_start)
                if pos < 4:
                    break
                box_size = int.from_bytes(data[pos - 4:pos], 'big')
                if (8 <= box_size <= 65536 or box_size == 1) and pos + 4 <= data_len:
                    start_offset = pos - 4
                    video_data = data[start_offset:]
                    if len(video_data) > 4096:
                        tmp_mp4 = os.path.join(
                            tempfile.gettempdir(),
                            f"motion_photo_{stem}_{start_offset}.mp4"
                        )
                        if not os.path.exists(tmp_mp4) or os.path.getsize(tmp_mp4) != len(video_data):
                            with open(tmp_mp4, 'wb') as vf:
                                vf.write(video_data)
                        return tmp_mp4
                search_start = pos + 1

            # 2b: moov 박스 역추적
            search_start = 0
            while True:
                pos = data.find(b'moov', search_start)
                if pos < 4:
                    break
                scan_start = max(0, pos - 65536)
                sub = data[scan_start:pos]
                sub_ftyp = sub.rfind(b'ftyp')
                if sub_ftyp != -1:
                    start_offset = scan_start + sub_ftyp - 4
                    video_data = data[start_offset:]
                    if len(video_data) > 4096:
                        tmp_mp4 = os.path.join(
                            tempfile.gettempdir(),
                            f"motion_photo_{stem}_{start_offset}.mp4"
                        )
                        if not os.path.exists(tmp_mp4) or os.path.getsize(tmp_mp4) != len(video_data):
                            with open(tmp_mp4, 'wb') as vf:
                                vf.write(video_data)
                        return tmp_mp4
                search_start = pos + 1

        except Exception as e:
            print(f"Motion Photo MP4 추출 오류: {e}")
        return None

    def check_file_has_audio(self, file_path, item=None):
        """[v4.64f FIX] 지정된 동영상/모션포토/MJPEG 추출 파일에 실제 오디오 스트림이 존재하는지 정밀 검사.
        반드시 실제 파일(motion_mp4 우선)을 ffprobe로 직접 검사한다."""
        if not file_path or not os.path.exists(file_path):
            return False
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            cmd = [self.ffprobe_path, '-v', 'error',
                   '-show_entries', 'stream=codec_type',
                   '-of', 'csv=p=0', file_path]
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding='utf-8', errors='replace',
                               creationflags=creationflags, timeout=4)
            if r.returncode == 0 and 'audio' in r.stdout.lower():
                return True
        except Exception:
            pass
        return False

    def check_file_real_duration(self, file_path):
        """[v4.647] 지정된 파일의 실제 재생 시간을 ffprobe로 정밀 측정.
        Motion Photo 추출 MP4의 실제 재생 시간이 item 메타데이터 duration보다
        짧을 경우, 마지막 프레임 freeze 현상이 발생하므로 실제 값 기반으로 처리."""
        if not file_path or not os.path.exists(file_path):
            return None
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            cmd = [self.ffprobe_path, '-v', 'error',
                   '-show_entries', 'format=duration',
                   '-of', 'csv=p=0', file_path]
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding='utf-8', errors='replace',
                               creationflags=creationflags, timeout=5)
            if r.returncode == 0 and r.stdout.strip():
                try:
                    d = float(r.stdout.strip().split('\n')[0])
                    if d > 0:
                        return d
                except (ValueError, IndexError):
                    pass
        except Exception:
            pass
        return None

    @staticmethod
    def check_mjpeg_binary_header(file_path):
        """[v4.653 FIX] 바이너리 오탐(EXIF b'jpeg', EXIF 썸네일 \xff\xd8)을 완벽 배제한 실효 MJPEG 헤더 검사"""
        MJPEG_FOURCC = {b'MJPG', b'mjpeg', b'MJPEG', b'dmb1', b'avi1', b'AVRN'}
        try:
            with open(file_path, 'rb') as f:
                header = f.read(4096)
                if not header:
                    return False
                
                # 1. 비디오 컨테이너 내 MJPEG FourCC 태그 검사 (b'jpeg' 등 일반 EXIF 태그 제외)
                for fourcc in MJPEG_FOURCC:
                    if fourcc in header:
                        return True
                
                # 2. Motion/Live Photo 마커 검사 (b'motionphoto', b'livephoto')
                low_h = header.lower()
                if any(k in low_h for k in [b'motionphoto', b'livephoto']):
                    return True
        except Exception:
            pass
        return False

    def _add_to_tree(self, info):
        info['checked'] = False
        item_id = info['id']
        if self.tree.exists(item_id):
            return
        rot_disp = self.get_rotation_display(info.get('rotate', '0'))
        self.tree.insert("", "end", iid=item_id, values=(
            "☐", info.get('disp_name', info['name']), info['orig_codec'], info['orig_res'],
            rot_disp, info['orig_bitrate'], info['orig_size'],
            "자동 계산 중", "계산 중...", "0.0% ─", "-", "대기 중"
        ))
        self._update_chk_header_state()
        self.update_estimations()

    def remove_selected(self):
        """[v4.65c FIX] 대기열 목록에서 체크박스가 선택된(☑) 항목들을 일괄 삭제 (체크항목 없으면 선택 행 삭제)"""
        if self.check_is_running():
            return

        # 1. 체크박스가 선택된(☑) 항목들의 ID 우선 추출
        to_delete = [f['id'] for f in self.file_list if f.get('checked', False)]

        # 2. 체크된 항목이 하나도 없으면 마우스로 선택(파란색 하이라이트)된 행 추출
        if not to_delete:
            to_delete = list(self.tree.selection())

        if not to_delete:
            return

        for item_id in to_delete:
            if self.tree.exists(item_id):
                self.tree.delete(item_id)
            self.file_list = [f for f in self.file_list if f['id'] != item_id]

        self._update_chk_header_state()
        self._refresh_auto_quality_profile_options()

        if not self.file_list:
            self.auto_quality_profile_var.set("")
            self.crf_global_apply_confirmed = False
            self.precise_quality_running = False
            self.precise_quality_generation += 1
            self._set_auto_quality_status("자동화질 준비", "#6b7280")
            self.lbl_stats.config(text="대기 중입니다.")
            self.progress['value'] = 0
            self.btn_start.config(state="normal")
            self.btn_cancel.config(state="disabled")
        else:
            self.lbl_stats.config(text=f"총 {len(self.file_list)}개 파일 준비 완료")
        self.update_estimations()

    @staticmethod
    def copy_file_timestamps(src_path, dst_path):
        """[v4.65c NEW] 원본 파일의 수정 시각(mtime), 접근 시각(atime), 및 생성 시각(ctime)을 생성된 결과 파일에 완벽 복사.
        (단일 파일은 해당 원본, 병합 파일은 맨 첫 번째 원본 파일 기준 적용)"""
        try:
            if not src_path or not dst_path or not os.path.exists(src_path) or not os.path.exists(dst_path):
                return
            st = os.stat(src_path)
            # 1. os.utime으로 access time과 modification time 복사
            os.utime(dst_path, (st.st_atime, st.st_mtime))

            # 2. Windows 환경일 경우 Win32 API(ctypes)를 이용해 파일 생성 시각(Creation Time)까지 복사
            if os.name == 'nt':
                try:
                    import ctypes
                    from ctypes import wintypes

                    class FILETIME(ctypes.Structure):
                        _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

                    def time_to_filetime(ns_time):
                        ft_val = int(ns_time * 10000000) + 116444736000000000
                        return FILETIME(ft_val & 0xFFFFFFFF, (ft_val >> 32) & 0xFFFFFFFF)

                    src_ctime = getattr(st, 'st_birthtime', None) or getattr(st, 'st_ctime', None) or st.st_mtime
                    ft_creation = time_to_filetime(src_ctime)
                    ft_access = time_to_filetime(st.st_atime)
                    ft_write = time_to_filetime(st.st_mtime)

                    kernel32 = ctypes.windll.kernel32
                    handle = kernel32.CreateFileW(
                        str(dst_path),
                        0x0100,  # FILE_WRITE_ATTRIBUTES
                        0,
                        None,
                        3,       # OPEN_EXISTING
                        0x02000000, # FILE_FLAG_BACKUP_SEMANTICS
                        None
                    )
                    if handle and handle != -1:
                        kernel32.SetFileTime(handle, ctypes.byref(ft_creation), ctypes.byref(ft_access), ctypes.byref(ft_write))
                        kernel32.CloseHandle(handle)
                except Exception as ex:
                    print(f"[v4.65c] Windows 생성시각 복사 중 경고: {ex}")
        except Exception as e:
            print(f"[v4.65c] 타임스탬프 복사 오류: {e}")

    # ==================================================================
    #  인코딩 인자 생성 (본작업/미리보기 공용)
    # ==================================================================
    def build_video_encode_args(self, crf_value=None, item=None, gui_snapshot=None, force_cpu=False):
        """[v4.66] UI 설정 기준 비디오 인코딩 인자 생성 (하이브리드 GPU 디코딩/필터링 + CPU 인코딩 파이프라인 지원)."""
        hw = gui_snapshot.get('combo_hw', '') if gui_snapshot else (self.combo_hw.get() if hasattr(self, 'combo_hw') else '')
        if force_cpu:
            hw = "CPU 전용"

        codec = self.get_item_codec(item, gui_snapshot)
        if crf_value is not None:
            crf_i = int(crf_value)
        elif gui_snapshot and 'crf' in gui_snapshot:
            crf_i = int(gui_snapshot['crf'])
        else:
            crf_i = self.crf_var.get() if hasattr(self, 'crf_var') else 28
        crf = str(crf_i)

        if "MKV" in codec or "H.265" in codec:
            family = 'hevc'
        elif "AV1" in codec:
            family = 'av1'
        elif "VP9" in codec:
            family = 'vp9'
        else:
            family = 'h264'

        qp_av1 = str(max(1, min(255, crf_i * 4)))

        table = {
            'hevc': {
                'AMD': ('hevc_amf', ['-quality', 'quality', '-rc', 'cqp', '-qp_i', crf, '-qp_p', crf]),
                'NVIDIA': ('hevc_nvenc', ['-preset', 'p6', '-cq', crf, '-spatial-aq', '1', '-temporal-aq', '1']),
                'Intel': ('hevc_qsv', ['-preset', 'medium', '-global_quality', crf, '-look_ahead', '1']),
                'CPU': ('libx265', ['-crf', crf, '-preset', 'medium']),
            },
            'av1': {
                'AMD': ('av1_amf', ['-quality', 'quality', '-rc', 'cqp', '-qp_i', qp_av1, '-qp_p', qp_av1]),
                'NVIDIA': ('av1_nvenc', ['-preset', 'p6', '-cq', crf, '-spatial-aq', '1', '-temporal-aq', '1']),
                'Intel': ('av1_qsv', ['-preset', 'medium', '-global_quality', crf, '-look_ahead', '1']),
                'CPU': ('libsvtav1', ['-crf', crf, '-preset', '6'])
                       if self.test_encoder_works('libsvtav1')
                       else ('libaom-av1', ['-crf', crf, '-cpu-used', '4', '-row-mt', '1', '-tiles', '2x2']),
            },
            'vp9': {
                'CPU': ('libvpx-vp9', ['-crf', crf, '-b:v', '0', '-row-mt', '1', '-tile-columns', '2']),
            },
            'h264': {
                'AMD': ('h264_amf', ['-quality', 'quality', '-rc', 'cqp', '-qp_i', crf, '-qp_p', crf]),
                'NVIDIA': ('h264_nvenc', ['-preset', 'p6', '-cq', crf, '-spatial-aq', '1', '-temporal-aq', '1']),
                'Intel': ('h264_qsv', ['-preset', 'medium', '-global_quality', crf]),
                'CPU': ('libx264', ['-crf', crf, '-preset', 'medium']),
            },
        }[family]

        cpu_encoder, cpu_args = table['CPU']
        vendor = 'AMD' if 'AMD' in hw else ('NVIDIA' if 'NVIDIA' in hw else ('Intel' if 'Intel' in hw else None))
        
        is_hybrid_mode = False
        if vendor and vendor in table:
            hw_encoder, hw_args = table[vendor]
            if self.test_encoder_works(hw_encoder):
                encoder, q_args = hw_encoder, hw_args
            else:
                # HW 인코더 미지원 GPU (예: RX 6600 AV1, GTX 1080 AV1 등) -> 하이브리드 파이프라인 (GPU 디코딩+필터링 + CPU 인코딩)
                encoder, q_args = cpu_encoder, cpu_args
                is_hybrid_mode = True
        else:
            encoder, q_args = cpu_encoder, cpu_args

        args = []

        # 하이브리드 GPU 디코딩 전처리 입력 플래그
        if is_hybrid_mode and not force_cpu:
            if vendor == 'NVIDIA':
                args.extend(['__HW_INPUT__', '-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda'])
            elif vendor == 'AMD':
                args.extend(['__HW_INPUT__', '-hwaccel', 'd3d11va', '-hwaccel_output_format', 'd3d11'])
            elif vendor == 'Intel':
                args.extend(['__HW_INPUT__', '-hwaccel', 'qsv', '-hwaccel_output_format', 'qsv'])

        args.extend(['-c:v', encoder])
        args.extend(q_args)

        vf_chain = []
        if item:
            rot_f = self.get_rotation_filter(item.get('rotate', '0'))
            if rot_f:
                vf_chain.append(rot_f)

        res = gui_snapshot.get('combo_res', '') if gui_snapshot else (self.combo_res.get() if hasattr(self, 'combo_res') else "원본 유지")
        tw, th, vf_scale, _ = self.parse_resolution_setting(res)
        fit_choice = gui_snapshot.get('merge_fit', '') if gui_snapshot else (self.combo_merge_fit.get() if hasattr(self, 'combo_merge_fit') and self.combo_merge_fit else "")

        if vf_scale:
            if tw and th and ("꽉 채우기" in fit_choice or "Cover" in fit_choice):
                target_scale = f"scale={tw}:{th}:force_original_aspect_ratio=increase,crop={tw}:{th}"
            elif tw and th and ("자동 맞춤" in fit_choice or "Contain" in fit_choice):
                target_scale = f"scale={tw}:{th}:force_original_aspect_ratio=decrease,pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2"
            elif tw and th and ("가운데 정렬" in fit_choice or "Center" in fit_choice):
                target_scale = f"crop='min(iw,{tw})':'min(ih,{th})',pad={tw}:{th}:({tw}-iw)/2:({th}-ih)/2"
            else:
                target_scale = vf_scale

            if is_hybrid_mode and not force_cpu:
                if vendor == 'NVIDIA':
                    vf_chain.append(f"scale_cuda={tw}:{th},hwdownload,format=nv12")
                elif vendor == 'AMD':
                    vf_chain.append(f"scale_d3d11={tw}:{th},hwdownload,format=nv12")
                elif vendor == 'Intel':
                    vf_chain.append(f"scale_qsv={tw}:{th},hwdownload,format=nv12")
                else:
                    vf_chain.append(target_scale)
            else:
                vf_chain.append(target_scale)
        elif is_hybrid_mode and not force_cpu:
            vf_chain.append("hwdownload,format=nv12")

        is_merge_cap = gui_snapshot.get('merge_caption_mode', False) if gui_snapshot else (self.merge_caption_mode.get() if hasattr(self, 'merge_caption_mode') else False)
        if item and is_merge_cap:
            cap_dur_mode = gui_snapshot.get('caption_duration_var', '계속') if gui_snapshot else (self.caption_duration_var.get() if hasattr(self, 'caption_duration_var') else '계속')
            if cap_dur_mode != '표시 안함':
                stem = Path(item.get('path', '')).stem if item.get('path') else ''
                if stem:
                    caption_theme = gui_snapshot.get('caption_theme_var', '🌈 레인보우 네온 (기본값)') if gui_snapshot else (self.caption_theme_var.get() if hasattr(self, 'caption_theme_var') else '🌈 레인보우 네온 (기본값)')
                    if '계속' in cap_dur_mode:
                        cap_sec = item.get('duration', 9999) or 9999
                    else:
                        try:
                            cap_sec = float(gui_snapshot.get('caption_custom_sec', '5')) if gui_snapshot else float(self.caption_custom_sec.get())
                        except (ValueError, TypeError):
                            cap_sec = 5.0
                    cap_f = self.build_caption_drawtext_filter(stem, duration=cap_sec, theme_name=caption_theme)
                    if cap_f:
                        vf_chain.append(cap_f)

        is_mjpeg_src = item and (item.get('is_static_photo') or 'MJPEG' in str(item.get('orig_codec', '')).upper() or 'JPEG' in str(item.get('orig_codec', '')).upper())
        if is_mjpeg_src or family in ('av1', 'hevc', 'h264', 'vp9'):
            vf_chain.append("format=yuv420p")

        if vf_chain:
            args.extend(['-vf', ",".join(vf_chain)])

        fps = gui_snapshot.get('combo_fps', '원본 유지') if gui_snapshot else (self.combo_fps.get() if hasattr(self, 'combo_fps') else "원본 유지")
        if fps != "원본 유지":
            args.extend(['-r', fps])

        return args

    def compute_fast_file_hash(self, filepath):
        """[v4.62] 대용량 동영상 및 사진의 내용을 0.01초 만에 검증하는 고속 하이브리드 해시 계산"""
        try:
            p = Path(filepath)
            if not p.exists() or not p.is_file():
                return None
            size = p.stat().st_size
            if size == 0:
                return f"empty_0"
            md5 = hashlib.md5()
            md5.update(str(size).encode('utf-8'))
            chunk_size = 64 * 1024
            with open(p, 'rb') as f:
                if size <= chunk_size * 3:
                    md5.update(f.read())
                else:
                    md5.update(f.read(chunk_size))
                    f.seek(size // 2)
                    md5.update(f.read(chunk_size))
                    f.seek(size - chunk_size)
                    md5.update(f.read(chunk_size))
            return f"{size}_{md5.hexdigest()}"
        except Exception:
            return None

    def filter_duplicates_in_queue(self, show_msg=True):
        """[v4.62] 대기열 내 내용이 동일한 영상/사진 중복 검사 및 자동 제외 처리"""
        if not hasattr(self, 'file_list') or not self.file_list:
            if show_msg:
                AppMessageBox.showinfo("중복 검사 안내", "대기열에 검사할 파일이 없습니다.", parent=self.root)
            return 0

        seen_hashes = {}
        dup_count = 0
        excluded_names = []

        for item in self.file_list:
            if item.get('status') == "완료":
                continue

            h = self.compute_fast_file_hash(item['path'])
            if not h:
                continue

            if h in seen_hashes:
                first_name = seen_hashes[h]['name']
                item['checked'] = False
                item['status'] = f"🚫 중복 제외됨 ('{first_name}'과 동일)"
                try:
                    self.tree.set(item['id'], "chk", "☐")
                    self.tree.set(item['id'], "status", f"🚫 중복 제외됨 ('{first_name}'과 동일)")
                except Exception:
                    pass
                dup_count += 1
                excluded_names.append(f"• {item['name']} ↔ '{first_name}'")
            else:
                seen_hashes[h] = item

        if dup_count > 0:
            self.update_estimations()
            if show_msg:
                sample_list = "\n".join(excluded_names[:5])
                if len(excluded_names) > 5:
                    sample_list += f"\n... 외 {len(excluded_names)-5}개"
                AppMessageBox.showinfo(
                    "🔍 중복 파일 탐색 및 제외 완료",
                    f"총 {dup_count}개의 동일한 내용의 중복 파일(영상/사진)을 발견하여 대기열에서 제외(☐) 처리했습니다.\n\n"
                    f"[제외된 중복 파일 목록 일부]\n{sample_list}",
                    parent=self.root
                )
        else:
            if show_msg:
                AppMessageBox.showinfo("🔍 중복 파일 검사 완료", "대기열에 내용이 완전히 동일한 중복 파일이 없습니다.", parent=self.root)

        return dup_count

    def build_caption_drawtext_filter(self, filename_stem, duration=5.0, theme_name=None):
        """[v4.631] 영상 구간 시작 시 우측 하단 둥근 사각형 박스 안에
        선택한 자막 색상 테마와 함께 지정 시간만큼 페이드 인/아웃으로 표시하는 FFmpeg drawtext 필터.
        duration >= 9000이면 '계속' 모드로 항상 표시.
        """
        if not filename_stem:
            return ""

        safe_text = (filename_stem
                     .replace('\\', '\\\\')
                     .replace("'", "'\\''")
                     .replace(':', '\\:')
                     .replace('%', '\\%'))

        font_path = "C\\:/Windows/Fonts/malgun.ttf"
        if not os.path.exists("C:/Windows/Fonts/malgun.ttf"):
            font_path = "C\\:/Windows/Fonts/arial.ttf"

        # [v4.646] duration에 따른 동적 alpha 표현식 생성 ('계속' 모드는 페이드 없이 100% 지속 선명 노출)
        d = float(duration) if isinstance(duration, (int, float, str)) and str(duration).replace('.', '', 1).isdigit() else 9999.0
        if d >= 9000 or '계속' in str(duration):
            # '계속' 모드: 페이드인/아웃 전면 제거 (100% 또렷한 선명도 지속 유지)
            alpha_expr = "1"
        elif d <= 2:
            # 짧은 표시: 빠른 페이드
            fi = min(0.3, d * 0.2)
            fo_start = d - fi
            alpha_expr = f"if(lt(t,{fi:.1f}),t/{fi:.1f},if(lt(t,{fo_start:.1f}),1,if(lt(t,{d:.1f}),({d:.1f}-t)/{fi:.1f},0)))"
        else:
            # 일반 표시: 0.8초 페이드인, 0.8초 페이드아웃
            fi = 0.8
            fo_start = d - 0.8
            alpha_expr = f"if(lt(t,{fi}),t/{fi},if(lt(t,{fo_start:.1f}),1,if(lt(t,{d:.1f}),({d:.1f}-t)/{fi},0)))"

        theme = CAPTION_THEMES.get(theme_name, CAPTION_THEMES["🤍 미니멀 글래스 (기본값)"])
        # [v4.649] 사용자 지정 팔레트 색상이 지정되어 있으면 우선 반영, 아니면 테마 폰트 색상 사용 (기본 단색 흰색)
        fc = getattr(self, 'custom_caption_color', None) or theme.get('fontcolor', '#ffffff')
        bw = '0'  # [v4.649] 텍스트 외곽 테두리 전면 제거 (borderw=0, 깔끔한 단색 폰트)
        boxc = theme.get('boxcolor', '#0f172a@0.65')
        boxbw = theme.get('boxborderw', '10')

        # [v4.65e FIX] FFmpeg drawtext 필터에서 '#RRGGBB@alpha' → '0xRRGGBB@alpha' 치환
        # FFmpeg 필터 파서가 '#' 기호를 주석이나 구분자로 오인하여 Syntax error를 일으키므로
        # 모든 색상값에서 '#' → '0x' 로 변환하여 전달한다.
        def _ffmpeg_color(c):
            if isinstance(c, str) and c.startswith('#'):
                return '0x' + c[1:]
            return c
        fc = _ffmpeg_color(fc)
        boxc = _ffmpeg_color(boxc)

        filter_str = (
            f"drawtext=fontfile='{font_path}':text='{safe_text}':fontsize=h/38:"
            f"fontcolor={fc}:borderw={bw}:"
            f"box=1:boxcolor={boxc}:boxborderw={boxbw}:"
            f"x=w-tw-30:y=h-th-30:alpha='{alpha_expr}'"
        )
        return filter_str

    @staticmethod
    def get_rotation_filter(rot_code):
        """[v4.61] 회전 / 좌우 반전 FFmpeg 필터 문자열 반환"""
        if rot_code == '90_cw':
            return 'transpose=1'
        elif rot_code == '90_ccw':
            return 'transpose=2'
        elif rot_code == '180':
            return 'transpose=2,transpose=2'
        elif rot_code == 'hflip':
            return 'hflip'
        return ""

    @staticmethod
    def get_rotation_display(rot_code):
        table = {
            '0': "🔄 0° (기본)",
            '90_cw': "↷ 90°(우)",
            '90_ccw': "↶ 90°(좌)",
            '180': "🙃 180°",
            'hflip': "↔️ 좌우반전"
        }
        return table.get(str(rot_code), "🔄 0° (기본)")

    def set_selected_rotation(self, rot_code):
        selected = self.tree.selection()
        if not selected:
            return
        disp = self.get_rotation_display(rot_code)
        for row_id in selected:
            item = next((f for f in self.file_list if f['id'] == row_id), None)
            if item:
                item['rotate'] = rot_code
                self.tree.set(row_id, "rotate", disp)
        self.update_estimations()

    def show_rotation_menu_selected(self):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="🔄 0° (회전 없음 / 기본)", command=lambda: self.set_selected_rotation('0'))
        menu.add_command(label="↷ 오른쪽 90° 회전 (시계 방향)", command=lambda: self.set_selected_rotation('90_cw'))
        menu.add_command(label="↶ 왼쪽 90° 회전 (반시계 방향)", command=lambda: self.set_selected_rotation('90_ccw'))
        menu.add_command(label="🙃 180° 회전", command=lambda: self.set_selected_rotation('180'))
        menu.add_command(label="↔️ 좌우 반전 (Horizontal Flip)", command=lambda: self.set_selected_rotation('hflip'))

        try:
            x = self.root.winfo_pointerx()
            y = self.root.winfo_pointery()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def cycle_rotation(self, item_id):
        item = next((f for f in self.file_list if f['id'] == item_id), None)
        if not item:
            return
        order = ['0', '90_cw', '90_ccw', '180', 'hflip']
        cur = str(item.get('rotate', '0'))
        next_idx = (order.index(cur) + 1) % len(order) if cur in order else 0
        new_rot = order[next_idx]
        item['rotate'] = new_rot
        self.tree.set(item_id, "rotate", self.get_rotation_display(new_rot))
        self.update_estimations()

    #  [v3.0] MP4 컨테이너에 재인코딩 없이 담을 수 있는 오디오 코덱 목록
    MP4_SAFE_AUDIO = {'aac', 'mp3', 'ac3', 'eac3', 'alac'}

    def audio_copy_selected(self):
        a = getattr(self, 'combo_audio', None)
        if not a:
            return False
        val = a.get()
        return "원본" in val and "음소거" not in val

    def audio_mute_selected(self):
        """[v4.646] 음소거 모드: 오디오 트랙 완전 제거 옵션 여부 반환"""
        a = getattr(self, 'combo_audio', None)
        return bool(a) and ("음소거" in a.get() or "mute" in a.get().lower())

    def get_audio_bitrate(self):
        """레이블/리포트용 오디오 설정 문자열 (재인코딩 시의 비트레이트)"""
        a = getattr(self, 'combo_audio', None)
        if a:
            val = a.get()
            if "음소거" in val or "mute" in val.lower():
                return "🔇 음소거 (소리 제거)"
            if "원본" in val:
                return "원본 유지 (무변환 복사)"
            if "192" in val:
                return "192k"
            if "96" in val:
                return "96k"
        return "128k"

    def get_audio_encode_bitrate(self):
        """실제 -b:a 에 들어갈 비트레이트 (재인코딩이 필요한 경우)"""
        a = getattr(self, 'combo_audio', None)
        if a:
            val = a.get()
            if "음소거" in val or "mute" in val.lower():
                return None  # 음소거 모드: 반환값으로 -an 처리 구분
            if "192" in val:
                return "192k"
            if "96" in val:
                return "96k"
        return "128k"

    # [v3.0] MP4/MKV 컨테이너 안전 오디오 코덱 목록
    MP4_SAFE_AUDIO = {'aac', 'mp3', 'ac3', 'eac3', 'alac'}
    MKV_SAFE_AUDIO = {'aac', 'mp3', 'ac3', 'eac3', 'alac', 'flac', 'opus', 'vorbis', 'dts'}

    def build_audio_args(self, item=None, container_ext=".mp4", gui_snapshot=None):
        """[v4.65d FIX] 오디오 인자 생성 (백그라운드 스레드 안전)."""
        _abits = gui_snapshot.get('audio_bitrate', '') if gui_snapshot else (self.get_audio_encode_bitrate() or '128k')
        if '음소거' in str(_abits) or 'mute' in str(_abits).lower() or _abits == 'none':
            return ['-an']
        _is_copy = gui_snapshot.get('audio_copy', False) if gui_snapshot else self.audio_copy_selected()
        if _is_copy:
            src_codec = str((item or {}).get('audio_codec', '')).lower()
            safe_set = self.MKV_SAFE_AUDIO if container_ext == ".mkv" else self.MP4_SAFE_AUDIO
            if src_codec and src_codec in safe_set:
                return ['-c:a', 'copy']
            if not src_codec:
                return ['-c:a', 'copy']
            bitrate = gui_snapshot.get('audio_bitrate', '128k') if gui_snapshot else (self.get_audio_encode_bitrate() or '128k')
            if not bitrate or bitrate in ('None', '음소거', None):
                bitrate = '128k'
            return ['-c:a', 'aac', '-b:a', bitrate]
        bitrate = gui_snapshot.get('audio_bitrate', '128k') if gui_snapshot else (self.get_audio_encode_bitrate() or '128k')
        if not bitrate or bitrate in ('None', '음소거', None):
            return ['-an']
        return ['-c:a', 'aac', '-b:a', bitrate]

    # ==================================================================
    #  [v3.2] 작업대기열 더블클릭: 10초 좌우 동시 비교 재생
    # ==================================================================
    def _get_item_by_id(self, item_id):
        """Treeview iid에 대응하는 파일 항목을 반환한다."""
        return next((f for f in self.file_list if f.get('id') == item_id), None)

    def start_queue_compare_preview(self, event=None):
        """[v3.9] 파일명 더블클릭 → 통합 '미리보기 (전/후 비교)' 팝업으로 연결한다."""
        item_id = ""
        if event is not None:
            try:
                if self.tree.identify('region', event.x, event.y) != 'cell':
                    return "break"
                item_id = self.tree.identify_row(event.y)
            except Exception:
                item_id = ""
        if not item_id:
            selected = self.tree.selection()
            item_id = selected[0] if selected else ""
        target = self._get_item_by_id(item_id)
        if not target:
            return "break"
        self._close_crf_combo()
        self._hide_crf_tooltip()
        try:
            self.tree.selection_set(item_id)
            self.tree.focus(item_id)
            self.tree.see(item_id)
        except Exception:
            pass
        self.start_preview(target=target)
        return "break"

    @staticmethod
    def _read_exact(pipe, size):
        """파이프에서 rawvideo 한 프레임 크기만큼 정확히 읽는다."""
        data = bytearray()
        while len(data) < size:
            chunk = pipe.read(size - len(data))
            if not chunk:
                break
            data.extend(chunk)
        return bytes(data)

    # ==================================================================
    #  미리보기 (전/후 비교)
    # ==================================================================




    def open_with_default_player(self, path):
        try:
            if os.name == 'nt':
                os.startfile(path)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', path])
            else:
                subprocess.Popen(['xdg-open', path])
        except Exception as e:
            messagebox.showerror("재생 실패", f"클립을 열 수 없습니다:\n{e}", parent=self.root)

    def show_preview_window(self, r):
        """[v3.9] 통합 전/후 비교 팝업.

        - 버튼·파일명 더블클릭 공용 UI (무작위 구간 인코딩 비교)
        - Pillow 설치 시 모든 배율에서 LANCZOS 고품질 렌더링 (모자이크 현상 해결)
        - 동시 재생/일시 정지: 좌(원본)/우(압축) 프레임 동기 재생 (음소거)
        - 돋보기: 최대 10배, 재생 중에도 유지·드래그 이동 가능
        """
        win = tk.Toplevel(self.root)
        win.title(f"미리보기 (전/후 비교) - {r['target']['name']}")
        win.configure(bg=self.BG_COLOR)
        win.transient(self.root)
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()

        # [v4.55 UX] 미리보기 영상 전체 해상도를 파악하여 창 크기 자동 확장 계산
        target_info = r.get('target', {})
        vw = target_info.get('orig_width') or 1280
        vh = target_info.get('orig_height') or 720
        res_label = r.get('res_label', '')
        tw, th, _, _ = self.parse_resolution_setting(res_label)
        if tw and th:
            vw, vh = tw, th
        elif th:
            vh = th

        target_w = min(1100, int(sw * 0.75))
        target_h = min(720, int(sh * 0.75))

        # 화면 크기를 초과하지 않도록 자동 제한 및 최소/최대 안전 크기 적용
        w0 = max(600, min(target_w, sw - 40))
        h0 = max(500, min(target_h, sh - 60))

        # [v4.55 UX] 실행 중인 메인 작업창의 정중앙 좌표점 기준으로 미리보기 팝업 배치
        try:
            self.root.update_idletasks()
            px, py = self.root.winfo_x(), self.root.winfo_y()
            pw, ph = self.root.winfo_width(), self.root.winfo_height()
            cx, cy = px + (pw // 2), py + (ph // 2)

            x = cx - (w0 // 2)
            y = cy - (h0 // 2)
        except Exception:
            x = (sw - w0) // 2
            y = (sh - h0) // 2

        # 창이 화면 밖으로 벗어나지 않도록 좌표 보정 (상하좌우 안전 여백)
        x = max(10, min(x, sw - w0 - 10))
        y = max(10, min(y, sh - h0 - 40))

        win.geometry(f"{w0}x{h0}+{x}+{y}")
        # [v3.9] 가로 폭을 기존(940)의 절반 수준까지 줄일 수 있게 완화
        win.minsize(470, 560)

        pst = {
            'win': win, 'result': r, 'closed': False,
            'fullscreen': False, 'zoom_on': True,
            'view_cx': 0.5, 'view_cy': 0.5, 'drag_last': None,
            'sources': {}, 'img_labels': {}, 'photos': [], 'scales': {},
            'resize_job': None, 'last_size': (0, 0),
            # 동시 재생 상태
            'playing': False, 'play_mode': False, 'elapsed': 0.0,
            'generation': 0, 'process': None, 'queue': queue.Queue(maxsize=2),
            'polling': False, 'fps': 12, 'last_play_frame': None,
            'play_scale': 1.0, 'play_box': (0, 0),
        }
        self.preview_popup_state = pst

        t_str = self.format_time(r['start_t'])
        info = tk.Label(
            win,
            text=(f"임의 장면 위치: 약 {t_str} 지점부터 {r['clip_len']:.1f}초 구간  |  "
                  f"설정: {r['codec_label']} / CRF {r['eff_crf']} / "
                  f"{r['res_label']} / {r['hw_label']}"),
            bg=self.BG_COLOR, fg=self.TEXT_SUB, font=("맑은 고딕", 9),
            wraplength=max(430, w0 - 60), justify="center")
        info.pack(pady=(10, 4))
        pst['info_label'] = info

        # 도구 막대: 전체화면 + 돋보기 모드 + 배율(최대 10배)
        toolbar = tk.Frame(win, bg=self.BG_COLOR)
        toolbar.pack(fill="x", padx=15, pady=(0, 4))
        btn_full = ttk.Button(toolbar, text="⛶ 전체화면", width=12,
                              command=lambda: self._pv_toggle_fullscreen(pst))
        btn_full.pack(side="left")
        pst['fullscreen_button'] = btn_full
        btn_zoom = ttk.Button(toolbar, text="🔍 돋보기: ON", width=13,
                              command=lambda: self._pv_toggle_zoom(pst))
        btn_zoom.pack(side="left", padx=(6, 0))
        pst['zoom_button'] = btn_zoom
        ttk.Label(toolbar, text="배율:").pack(side="left", padx=(8, 2))
        zoom_combo = ttk.Combobox(
            toolbar, values=["1.5배", "2배", "3배", "4배", "5배", "6배", "8배", "10배"],
            state="readonly", width=5)
        zoom_combo.set("5배")
        zoom_combo.pack(side="left")
        zoom_combo.bind("<<ComboboxSelected>>", lambda e: self._pv_on_zoom_change(pst))
        pst['zoom_combo'] = zoom_combo
        hint = tk.Label(toolbar,
                        text="돋보기 ON 후 드래그하면 전/후(재생 중 포함)가 같은 위치로 함께 이동합니다. (해제 시 위치 초기화)",
                        bg=self.BG_COLOR, fg="#b45309", font=("맑은 고딕", 8),
                        wraplength=430, justify="left")
        hint.pack(side="left", padx=(10, 0))
        pst['hint_label'] = hint

        body = tk.Frame(win, bg=self.BG_COLOR)
        body.pack(fill="both", expand=True, padx=15, pady=2)
        body.columnconfigure(0, weight=1, uniform="pv")
        body.columnconfigure(1, weight=1, uniform="pv")
        body.rowconfigure(0, weight=1)

        panels = [
            ("압축 전 (원본)", 'orig', r['frame_orig'], r['orig_clip_size'],
             r['orig_info'], r['orig_clip']),
            (f"압축 후 (CRF {r['eff_crf']})", 'comp', r['frame_comp'], r['comp_clip_size'],
             r['comp_info'], r['comp_clip']),
        ]
        for col, (title, key, img_path, clip_size, info_d, clip_path) in enumerate(panels):
            panel = tk.Frame(body, bg=self.CARD_BG, highlightbackground="#d1d5db",
                             highlightthickness=1)
            panel.grid(row=0, column=col, padx=4, sticky="nsew")
            panel.rowconfigure(1, weight=1)
            panel.columnconfigure(0, weight=1)

            tk.Label(panel, text=title, bg=self.CARD_BG, fg=self.TEXT_MAIN,
                     font=("맑은 고딕", 11, "bold")).grid(row=0, column=0, pady=(7, 3))

            img_label = tk.Label(panel, bg=self.CARD_BG, fg=self.TEXT_SUB,
                                 text="프레임 로딩 중...", font=("맑은 고딕", 9),
                                 cursor="fleur" if pst.get('zoom_on') else "")
            img_label.grid(row=1, column=0, sticky="nsew", padx=6)
            pst['img_labels'][key] = img_label
            self._pv_load_source(pst, key, img_path, img_label)
            img_label.bind("<ButtonPress-1>",
                           lambda e, k=key: self._pv_drag_start(pst, e, k))
            img_label.bind("<B1-Motion>", lambda e: self._pv_drag_move(pst, e))

            detail = f"{r['clip_len']:.1f}초 구간 크기: {self.format_size(clip_size)}"
            if info_d:
                detail += f"  |  코덱: {info_d['codec']}  |  비트레이트: {info_d['bitrate']}"
            tk.Label(panel, text=detail, bg=self.CARD_BG, fg=self.TEXT_SUB,
                     font=("맑은 고딕", 9), wraplength=420,
                     justify="center").grid(row=2, column=0, pady=3)

            ttk.Button(panel, text="▶ 클립 재생 (외부 플레이어)",
                       command=lambda p=clip_path: self.open_with_default_player(p)
                       ).grid(row=3, column=0, pady=(0, 8))

        # 하단 통계 요약
        stats = tk.Frame(win, bg=self.CARD_BG, highlightbackground="#d1d5db", highlightthickness=1)
        stats.pack(fill="x", padx=15, pady=(6, 4))

        if r['orig_clip_size'] > 0 and r['comp_clip_size'] > 0:
            saved_pct = (1 - r['comp_clip_size'] / r['orig_clip_size']) * 100
            summary = (f"클립 기준 압축률: {self.format_ratio_display(saved_pct)}   |   "
                       f"전체 파일 예상 결과: {self.format_size(r['target']['orig_size_b'])} → "
                       f"약 {self.format_size(r['est_full_size'])}")
            color = "#15803d" if saved_pct > 0 else "#b91c1c"
        else:
            summary = "통계를 계산할 수 없습니다."
            color = self.TEXT_SUB
        tk.Label(stats, text=summary, bg=self.CARD_BG, fg=color,
                 font=("맑은 고딕", 10, "bold"), wraplength=max(430, w0 - 80),
                 justify="center").pack(pady=6)

        # 하단 버튼: 동시 재생 / 일시 정지 / 재생 시간 / 다른 장면 / 닫기
        btns = tk.Frame(win, bg=self.BG_COLOR)
        btns.pack(pady=(0, 10))
        btn_play = ttk.Button(btns, text="▶ 동시 재생", width=13,
                              command=lambda: self._pv_play(pst))
        btn_play.pack(side="left", padx=4)
        pst['play_button'] = btn_play
        btn_pause = ttk.Button(btns, text="⏸ 일시 정지", width=12, state="disabled",
                               command=lambda: self._pv_pause(pst))
        btn_pause.pack(side="left", padx=4)
        pst['pause_button'] = btn_pause
        time_label = tk.Label(btns, text=f"0.0 / {r['clip_len']:.1f}초",
                              bg=self.BG_COLOR, fg=self.TEXT_SUB,
                              width=14, font=("맑은 고딕", 9))
        time_label.pack(side="left", padx=(2, 8))
        pst['time_label'] = time_label
        ttk.Button(btns, text="🎲 다른 장면으로 다시 미리보기",
                   command=lambda: self._pv_retry(pst)).pack(side="left", padx=4)
        ttk.Button(btns, text="닫기",
                   command=lambda: self._pv_close(pst)).pack(side="left", padx=4)

        win.protocol("WM_DELETE_WINDOW", lambda: self._pv_close(pst))
        win.bind("<Configure>", lambda e: self._pv_on_configure(pst, e))
        win.bind("<F11>", lambda e: self._pv_toggle_fullscreen(pst))
        win.bind("<Escape>", lambda e: self._pv_exit_fullscreen(pst))
        win.bind("<space>", lambda e: self._pv_toggle_play(pst))
        win.after(150, lambda: self._pv_render(pst))

    # ------------------------------------------------------------------
    #  [v3.9] 미리보기 팝업: 전체화면 / 돋보기 / 동시 재생 보조 메서드
    # ------------------------------------------------------------------
    def _pv_zoom_factor(self, pst):
        try:
            return float(str(pst['zoom_combo'].get()).replace('배', '').strip())
        except Exception:
            return 2.0

    def _pv_load_source(self, pst, key, img_path, img_label):
        """정지 비교 프레임을 로드한다. Pillow가 있으면 고품질 처리용 PIL 이미지로 보관."""
        try:
            if not os.path.exists(img_path) or os.path.getsize(img_path) == 0:
                raise FileNotFoundError("프레임 이미지 파일이 생성되지 않았습니다.")
            if PIL_SUPPORTED:
                pst['sources'][key] = Image.open(img_path).convert('RGB')
            else:
                pst['sources'][key] = tk.PhotoImage(master=pst['win'], file=img_path)
            self.root.after(10, lambda: self._pv_render(pst))
        except Exception as e:
            pst['sources'][key] = None
            img_label.config(text=f"(프레임 로딩 실패: {e})", fg="#fca5a5")

    @staticmethod
    def _pv_src_size(src_img):
        if PIL_SUPPORTED and isinstance(src_img, Image.Image):
            return src_img.size
        return src_img.width(), src_img.height()

    @staticmethod
    def _pv_approx_scale_photo(photo, ratio):
        """(Pillow 미설치 폴백) PhotoImage를 zoom/subsample 정수 조합으로 근사 배율 변환한다.

        [v3.8] 확대 시 zoom을 먼저 적용해 모자이크 블록 현상을 줄인다.
        반환: (변환된 PhotoImage, 실제 적용 배율)
        """
        if ratio <= 0:
            return photo, 1.0
        best_z, best_s, best_err = 1, 1, abs(1.0 - ratio)
        for s in range(1, 17):
            for z in range(1, 13):
                interm_w = photo.width() * z
                if interm_w > 12000:
                    continue
                err = abs(z / s - ratio)
                if err < best_err - 1e-9:
                    best_z, best_s, best_err = z, s, err
        img = photo
        if best_z > 1:
            img = img.zoom(best_z, best_z)
        if best_s > 1:
            img = img.subsample(best_s, best_s)
        return img, best_z / best_s

    def _pv_render_box(self, pst):
        """전/후 각 패널의 표시 영역 크기(픽셀)를 안정적으로 계산한다. (하단 버튼 찌그러짐 방지)"""
        win = pst['win']
        total_w = win.winfo_screenwidth() if pst.get('fullscreen') else win.winfo_width()
        total_h = win.winfo_screenheight() if pst.get('fullscreen') else win.winfo_height()
        box_w = max(150, (total_w - 70) // 2)
        box_h = max(120, total_h - 340)
        return box_w, box_h

    def _pv_render(self, pst):
        """정지 비교 프레임을 현재 창 크기·전체화면·돋보기 상태에 맞춰 다시 그린다.

        [v3.8] Pillow 설치 시 LANCZOS 리샘플링으로 돋보기 OFF·모든 배율에서
        모자이크 없이 부드럽게 표시한다.
        """
        win = pst.get('win')
        try:
            if win is None or not win.winfo_exists() or pst.get('closed'):
                return
        except Exception:
            return
        if pst.get('play_mode') and pst.get('last_play_frame'):
            self._pv_render_play_current(pst)
            return
        box_w, box_h = self._pv_render_box(pst)
        zoom_on = pst.get('zoom_on', False)
        zf = self._pv_zoom_factor(pst) if zoom_on else 1.0
        pst['photos'] = []
        for key in ('orig', 'comp'):
            src_img = pst['sources'].get(key)
            label = pst['img_labels'].get(key)
            if src_img is None or label is None:
                continue
            sw_, sh_ = self._pv_src_size(src_img)
            if sw_ <= 0 or sh_ <= 0:
                continue
            if zoom_on:
                # 돋보기 ON: 패널 종횡비(box_w:box_h)를 가득 채우도록 스케일링하여 상하/좌우 레터박스 완전 제거
                vw = max(2, int(round(sw_ / zf)))
                vh = max(2, int(round(sh_ / zf)))

                half_x = vw / 2 / sw_
                half_y = vh / 2 / sh_
                cx = min(1.0 - half_x, max(half_x, float(pst.get('view_cx', 0.5))))
                cy = min(1.0 - half_y, max(half_y, float(pst.get('view_cy', 0.5))))
                if key == 'orig':
                    pst['view_cx'], pst['view_cy'] = cx, cy

                x0 = max(0, min(sw_ - vw, int(round(cx * sw_ - vw / 2))))
                y0 = max(0, min(sh_ - vh, int(round(cy * sh_ - vh / 2))))
                scale = max(box_w / vw, box_h / vh)
                out_w = max(box_w, int(round(vw * scale)))
                out_h = max(box_h, int(round(vh * scale)))
                pst['scales'][key] = scale
            else:
                # 돋보기 OFF: 원본 비율 유지 축소
                fit = min(box_w / sw_, box_h / sh_)
                vw, vh, x0, y0 = sw_, sh_, 0, 0
                out_w = max(2, int(round(sw_ * fit)))
                out_h = max(2, int(round(sh_ * fit)))
                pst['scales'][key] = fit

            scale = out_w / vw if vw > 0 else 1.0
            try:
                if PIL_SUPPORTED and isinstance(src_img, Image.Image):
                    region = src_img.crop((x0, y0, x0 + vw, y0 + vh))
                    if (vw, vh) != (out_w, out_h):
                        resized = region.resize((out_w, out_h), Image.LANCZOS)
                    else:
                        resized = region
                    photo = ImageTk.PhotoImage(resized, master=win)
                    pst['scales'][key] = scale
                    pst['photos'].append(photo)
                    label.config(image=photo, text="")
                else:
                    if vw >= sw_ and vh >= sh_:
                        region = src_img
                    else:
                        region = tk.PhotoImage(master=win)
                        region.tk.call(str(region), 'copy', str(src_img),
                                       '-from', x0, y0, x0 + vw, y0 + vh, '-to', 0, 0)
                    scaled, actual = self._pv_approx_scale_photo(region, scale)
                    pst['scales'][key] = actual if actual > 0 else scale
                    if region is not src_img:
                        pst['photos'].append(region)
                    pst['photos'].append(scaled)
                    label.config(image=scaled, text="")
            except Exception as e:
                try:
                    label.config(text=f"표시 오류: {e}", image="")
                except Exception:
                    pass

    # ── 동시 재생 ────────────────────────────────────────────────
    def _pv_toggle_play(self, pst):
        if pst.get('closed'):
            return
        if pst.get('playing'):
            self._pv_pause(pst)
        else:
            self._pv_play(pst)

    def _pv_play(self, pst):
        """좌(원본)/우(압축) 클립을 같은 시점부터 프레임 동기 재생한다."""
        if pst.get('closed') or pst.get('playing'):
            return
        offset = float(pst.get('elapsed', 0.0))
        duration = float(pst['result']['clip_len'])
        if offset >= duration - 0.05:
            offset = 0.0
        self._pv_start_playback(pst, offset)

    def _pv_pause(self, pst):
        """재생 중인 좌/우 영상을 즉시 모두 정지하고 현재 프레임을 유지한다."""
        if pst.get('closed') or not pst.get('playing'):
            return
        self._pv_stop_decoder(pst)
        try:
            pst['play_button'].config(text="▶ 이어서 재생", state="normal")
            pst['pause_button'].config(state="disabled")
        except Exception:
            pass

    def _pv_start_playback(self, pst, offset):
        if pst.get('closed'):
            return
        self._pv_stop_decoder(pst)
        pst['elapsed'] = max(0.0, float(offset))
        pst['generation'] += 1
        generation = pst['generation']
        pst['playing'] = True
        pst['play_mode'] = True
        box_w, box_h = self._pv_render_box(pst)
        # [v4.5] 고화질 정밀 디코딩: 원본 해상도(최대 1920x1080)급으로 디코딩하여 돋보기 5배 확대 시 깍두기 모자이크 현상 완전 제거
        src_orig = pst['sources'].get('orig')
        if src_orig and PIL_SUPPORTED and isinstance(src_orig, Image.Image):
            orig_w, orig_h = src_orig.size
        else:
            orig_w, orig_h = 1920, 1080

        scale_ratio = min(1920 / max(1, orig_w), 1080 / max(1, orig_h), 1.0)
        side_w = max(640, int(round(orig_w * scale_ratio)))
        side_h = max(360, int(round(orig_h * scale_ratio)))
        side_w -= side_w % 2
        side_h -= side_h % 2

        pst['play_box'] = (side_w, side_h)
        pst['queue'] = queue.Queue(maxsize=2)
        try:
            pst['play_button'].config(text="▶ 재생 중...", state="disabled")
            pst['pause_button'].config(state="normal")
        except Exception:
            pass
        threading.Thread(
            target=self._pv_decode_thread,
            args=(pst, generation, pst['elapsed'], side_w, side_h),
            daemon=True,
        ).start()
        if not pst.get('polling'):
            pst['polling'] = True
            pst['win'].after(10, lambda: self._pv_poll_frames(pst))

    def _pv_decode_thread(self, pst, generation, offset, side_w, side_h):
        """단일 ffmpeg 프로세스로 좌/우 클립을 같은 시점에서 hstack 디코딩한다."""
        result = pst['result']
        duration = float(result['clip_len'])
        remaining = max(0.05, duration - offset)
        fps = int(pst.get('fps', 12))
        # [v4.5] 초고화질 스트림 디코딩 (Lanczos 고품질 스케일링으로 모자이크 깍두기 완벽 방지)
        filt = (
            f"[0:v]trim=start={offset:.6f}:duration={remaining:.6f},setpts=PTS-STARTPTS,"
            f"scale={side_w}:{side_h}:flags=lanczos[left];"
            f"[1:v]trim=start={offset:.6f}:duration={remaining:.6f},setpts=PTS-STARTPTS,"
            f"scale={side_w}:{side_h}:flags=lanczos[right];"
            f"[left][right]hstack=inputs=2,fps={fps},format=rgb24[out]"
        )
        cmd = [
            self.ffmpeg_path, '-hide_banner', '-loglevel', 'error',
            '-i', result['orig_clip'], '-i', result['comp_clip'],
            '-filter_complex', filt, '-map', '[out]', '-an',
            '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1',
        ]
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        proc = None
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
            pst['process'] = proc
            frame_size = side_w * 2 * side_h * 3
            frame_index = 0
            started = time.monotonic()
            while (not pst.get('closed') and pst.get('generation') == generation
                   and pst.get('playing')):
                frame = self._read_exact(proc.stdout, frame_size)
                if len(frame) != frame_size:
                    break
                target_time = started + frame_index / fps
                delay = target_time - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                elapsed = min(duration, offset + frame_index / fps)
                packet = (generation, frame, elapsed, side_w * 2, side_h)
                try:
                    pst['queue'].put_nowait(packet)
                except queue.Full:
                    try:
                        pst['queue'].get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        pst['queue'].put_nowait(packet)
                    except queue.Full:
                        pass
                frame_index += 1
        except Exception as e:
            if not pst.get('closed'):
                msg = str(e)
                self.root.after(
                    0, lambda m=msg: messagebox.showerror("동시 재생 오류", f"영상을 재생하지 못했습니다.\n{m}", parent=self.root))
        finally:
            if proc:
                try:
                    if proc.poll() is None:
                        proc.terminate()
                    proc.wait(timeout=1)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            if pst.get('process') is proc:
                pst['process'] = None
            if (not pst.get('closed') and pst.get('generation') == generation
                    and pst.get('playing')):
                self.root.after(0, self._pv_playback_finished, pst, generation)

    def _pv_poll_frames(self, pst):
        try:
            if pst.get('closed') or not pst['win'].winfo_exists():
                pst['polling'] = False
                return
        except Exception:
            pst['polling'] = False
            return
        if pst.get('playing'):
            newest = None
            try:
                while True:
                    newest = pst['queue'].get_nowait()
            except queue.Empty:
                pass
            if newest:
                generation, frame, elapsed, width, height = newest
                if generation == pst.get('generation'):
                    pst['last_play_frame'] = (frame, width, height)
                    self._pv_render_play_frame(pst, frame, width, height)
                    pst['elapsed'] = elapsed
                    try:
                        pst['time_label'].config(
                            text=f"{elapsed:.1f} / {pst['result']['clip_len']:.1f}초")
                    except tk.TclError:
                        pass
        pst['win'].after(15, lambda: self._pv_poll_frames(pst))

    def _pv_render_play_current(self, pst):
        packet = pst.get('last_play_frame')
        if packet:
            self._pv_render_play_frame(pst, *packet)

    def _pv_render_play_frame(self, pst, frame, width, height):
        """[v4.5] 재생 프레임을 좌/우 패널에 표시한다.
        - 돋보기 OFF: 화면 폭/높이에 완벽히 맞춰 재생 중 2배 확대 및 왜곡 현상 완전 방지.
        - 돋보기 ON: 고화질 LANCZOS 리샘플링으로 모자이크 제거 및 레터박스 없는 가득 찬 화면 렌더링.
        """
        dw = max(2, width // 2)
        dh = height
        box_w, box_h = self._pv_render_box(pst)
        zoom_on = pst.get('zoom_on', False)
        zf = max(1.1, float(pst.get('zoom_factor', 5.0))) if zoom_on else 1.0

        if zoom_on:
            # 돋보기 ON: 패널 종횡비(box_w:box_h)를 가득 채우도록 스케일링하여 상하/좌우 레터박스 완전 제거
            vw = max(2, int(round(dw / zf)))
            vh = max(2, int(round(dh / zf)))

            half_x = vw / 2 / dw
            half_y = vh / 2 / dh
            cx = min(1.0 - half_x, max(half_x, float(pst.get('view_cx', 0.5))))
            cy = min(1.0 - half_y, max(half_y, float(pst.get('view_cy', 0.5))))
            pst['view_cx'], pst['view_cy'] = cx, cy

            x0 = max(0, min(dw - vw, int(round(cx * dw - vw / 2))))
            y0 = max(0, min(dh - vh, int(round(cy * dh - vh / 2))))
            scale = max(box_w / vw, box_h / vh)
            out_w = max(box_w, int(round(vw * scale)))
            out_h = max(box_h, int(round(vh * scale)))
            pst['play_scale'] = scale
        else:
            # 돋보기 OFF: 원본 비율 유지 축소 (2배 확대현상 완전 방지)
            vw, vh, x0, y0 = dw, dh, 0, 0
            fit = min(box_w / dw, box_h / dh)
            out_w = max(2, int(round(dw * fit)))
            out_h = max(2, int(round(dh * fit)))
            pst['play_scale'] = fit

        new_photos = []
        try:
            if PIL_SUPPORTED:
                img = Image.frombuffer('RGB', (width, height), frame, 'raw', 'RGB', 0, 1)
                for key, off_x in (('orig', 0), ('comp', dw)):
                    label = pst['img_labels'].get(key)
                    if label is None:
                        continue
                    region = img.crop((off_x + x0, y0, off_x + x0 + vw, y0 + vh))
                    if (vw, vh) != (out_w, out_h):
                        # 선명한 재생 품질을 위한 LANCZOS 리샘플링 (모자이크 깍두기 완벽 제거)
                        resample = Image.LANCZOS
                        region = region.resize((out_w, out_h), resample)
                    photo = ImageTk.PhotoImage(region, master=pst['win'])
                    new_photos.append(photo)
                    label.config(image=photo, text="")
            else:
                stride = width * 3
                for key, off_x in (('orig', 0), ('comp', dw)):
                    label = pst['img_labels'].get(key)
                    if label is None:
                        continue
                    rows = []
                    x_start = (off_x + x0) * 3
                    x_end = (off_x + x0 + vw) * 3
                    for y in range(y0, y0 + vh):
                        base = y * stride
                        rows.append(frame[base + x_start: base + x_end])
                    ppm = f"P6\n{vw} {vh}\n255\n".encode('ascii') + b''.join(rows)
                    photo = tk.PhotoImage(data=ppm, format='PPM')
                    if (vw, vh) != (out_w, out_h):
                        photo, actual = self._pv_approx_scale_photo(photo, out_w / vw)
                        pst['play_scale'] = actual if actual > 0 else pst['play_scale']
                    new_photos.append(photo)
                    label.config(image=photo, text="")
            pst['photos'] = new_photos
        except tk.TclError:
            pass

    def _pv_playback_finished(self, pst, generation):
        if pst.get('closed') or generation != pst.get('generation'):
            return
        pst['playing'] = False
        pst['play_mode'] = False
        pst['last_play_frame'] = None
        pst['elapsed'] = 0.0
        q = pst.get('queue')
        if q:
            try:
                while True:
                    q.get_nowait()
            except queue.Empty:
                pass
        try:
            pst['time_label'].config(
                text=f"0.0 / {pst['result']['clip_len']:.1f}초 (재생 완료)")
            pst['play_button'].config(text="▶ 동시 재생", state="normal")
            pst['pause_button'].config(state="disabled")
        except Exception:
            pass
        # 재생 완료 후 원래 비교용 정지 프레임으로 복귀한다. (돋보기 상태 유지)
        self._pv_render(pst)

    def _pv_stop_decoder(self, pst):
        if not pst:
            return
        pst['playing'] = False
        pst['generation'] = pst.get('generation', 0) + 1
        proc = pst.get('process')
        if proc:
            pst['process'] = None
            if proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass
        q = pst.get('queue')
        if q:
            try:
                while True:
                    q.get_nowait()
            except queue.Empty:
                pass

    # ── 돋보기 / 전체화면 / 크기 변경 ─────────────────────────────
    def _pv_toggle_zoom(self, pst):
        """돋보기 ON/OFF. 재생 중에도 재생을 끊지 않고 즉시 반영된다."""
        pst['zoom_on'] = not pst.get('zoom_on', False)
        # 모드 전환(해제 포함) 시 확대 위치를 중앙으로 초기화
        pst['view_cx'] = 0.5
        pst['view_cy'] = 0.5
        cursor = "fleur" if pst['zoom_on'] else ""
        for label in pst['img_labels'].values():
            try:
                label.config(cursor=cursor)
            except Exception:
                pass
        try:
            pst['zoom_button'].config(
                text="🔍 돋보기: ON" if pst['zoom_on'] else "🔍 돋보기: OFF")
            pst['hint_label'].config(fg="#b45309" if pst['zoom_on'] else self.TEXT_SUB)
        except Exception:
            pass
        self._pv_render(pst)

    def _pv_on_zoom_change(self, pst):
        if pst.get('zoom_on'):
            self._pv_render(pst)

    def _pv_toggle_fullscreen(self, pst):
        try:
            pst['fullscreen'] = not pst.get('fullscreen', False)
            pst['win'].attributes('-fullscreen', pst['fullscreen'])
            pst['fullscreen_button'].config(
                text="⤢ 창 모드" if pst['fullscreen'] else "⛶ 전체화면")
        except Exception:
            return
        pst['win'].after(200, lambda: self._pv_apply_new_size(pst))

    def _pv_exit_fullscreen(self, pst):
        if not pst.get('fullscreen'):
            return
        try:
            pst['fullscreen'] = False
            pst['win'].attributes('-fullscreen', False)
            pst['fullscreen_button'].config(text="⛶ 전체화면")
        except Exception:
            return
        pst['win'].after(200, lambda: self._pv_apply_new_size(pst))

    def _pv_apply_new_size(self, pst):
        """전체화면 전환·창 크기 변경 후: 재생 중이면 새 해상도로 같은 위치부터 재시작한다."""
        if pst.get('closed'):
            return
        if pst.get('playing'):
            self._pv_start_playback(pst, float(pst.get('elapsed', 0.0)))
        else:
            self._pv_render(pst)

    def _pv_on_configure(self, pst, event):
        if event.widget is not pst.get('win') or pst.get('closed'):
            return
        size = (event.width, event.height)
        if size == pst.get('last_size'):
            return
        pst['last_size'] = size
        try:
            pst['info_label'].config(wraplength=max(430, event.width - 60))
        except Exception:
            pass
        if pst.get('resize_job'):
            try:
                pst['win'].after_cancel(pst['resize_job'])
            except Exception:
                pass
        pst['resize_job'] = pst['win'].after(300, lambda: self._pv_apply_new_size(pst))


    # ── 드래그 이동 (정지/재생 공용) ──────────────────────────────
    def _pv_drag_start(self, pst, event, key):
        pst['drag_last'] = (event.x, event.y, key)

    def _pv_drag_move(self, pst, event):
        if not pst.get('zoom_on'):
            return
        last = pst.get('drag_last')
        if not last:
            return
        dx = event.x - last[0]
        dy = event.y - last[1]
        key = last[2]
        pst['drag_last'] = (event.x, event.y, key)
        if pst.get('play_mode') and pst.get('last_play_frame'):
            # 재생(일시 정지 포함) 화면: 디코딩된 좌/우 절반 프레임 좌표 기준으로 환산
            _, width, height = pst['last_play_frame']
            dw = max(2, width // 2)
            dh = max(2, height)
            sc = max(0.01, float(pst.get('play_scale', 1.0)))
            pst['view_cx'] = min(1.0, max(0.0, pst['view_cx'] - (dx / sc) / dw))
            pst['view_cy'] = min(1.0, max(0.0, pst['view_cy'] - (dy / sc) / dh))
            self._pv_render_play_current(pst)
            return
        src_img = pst['sources'].get(key) or pst['sources'].get('orig')
        if src_img is None:
            return
        sc = pst['scales'].get(key) or 1.0
        sw_, sh_ = self._pv_src_size(src_img)
        if sw_ <= 0 or sh_ <= 0 or sc <= 0:
            return
        # 드래그한 패널 기준으로 환산하되 정규화 좌표를 공유해 전/후가 함께 이동한다.
        pst['view_cx'] = min(1.0, max(0.0, pst['view_cx'] - (dx / sc) / sw_))
        pst['view_cy'] = min(1.0, max(0.0, pst['view_cy'] - (dy / sc) / sh_))
        self._pv_render(pst)

    # ── 팝업 닫기 / 다른 장면 ────────────────────────────────────
    def _pv_retry(self, pst):
        """같은 파일의 다른 무작위 구간으로 다시 미리보기를 만든다."""
        target = pst['result']['target']
        self._pv_close(pst)
        self.start_preview(target=target)

    def _pv_close(self, pst=None):
        pst = pst or self.preview_popup_state
        if not pst or pst.get('closed'):
            return
        pst['closed'] = True
        self._pv_stop_decoder(pst)
        try:
            if pst['win'].winfo_exists():
                pst['win'].destroy()
        except Exception:
            pass
        if self.preview_popup_state is pst:
            self.preview_popup_state = None
        try:
            self.lbl_stats.config(text="대기 중...")
        except Exception:
            pass

    # ==================================================================
    #  배치 압축 실행
    # ==================================================================
    def start_batch(self):
        if self.precise_quality_running:
            messagebox.showinfo("자동화질 계산 중",
                                "정밀 자동화질 계산이 끝난 후 일괄 압축을 시작해주세요.", parent=self.root)
            return
        if not self.file_list:
            messagebox.showinfo("안내", "처리할 파일을 먼저 추가해주세요.", parent=self.root)
            return
        if not self.ffmpeg_path:
            messagebox.showwarning("안내", "FFmpeg가 설치되어 있지 않습니다.\n[도구] 메뉴에서 코덱을 먼저 설치해주세요.", parent=self.root)
            return

        self._close_crf_combo()

        # [v3.0] 지정 저장 폴더 사전 검사
        if self.output_mode.get() == 'custom':
            if not self.output_dir:
                messagebox.showwarning("안내", "저장 위치가 '지정 폴더'로 설정되어 있지만\n"
                                               "폴더가 선택되지 않았습니다. [찾아보기...]로 지정해주세요.", parent=self.root)
                return
            try:
                base = Path(self.output_dir)
                base.mkdir(parents=True, exist_ok=True)
                probe = base / f".write_test_{os.getpid()}.tmp"
                with open(probe, 'w', encoding='utf-8') as f:
                    f.write('ok')
                probe.unlink()
            except OSError as e:
                messagebox.showerror("저장 폴더 오류",
                                     f"지정한 저장 폴더에 쓸 수 없습니다.\n{self.output_dir}\n\n{e}", parent=self.root)
                return
        # [v4.52] 일괄 압축 시작 시: 체크박스(#1)로 직접 특정 항목을 해제한 경우가 아니라면 미완료 전 항목 자동 체크(☑) 처리
        uncompleted = [item for item in self.file_list if item.get('status') != "완료"]
        if not uncompleted:
            messagebox.showinfo("안내", "대기열에 처리할 대기 파일이 없습니다.", parent=self.root)
            return

        has_manual_uncheck = any(not item.get('checked', True) and item.get('manually_checked', False) for item in uncompleted)
        if not has_manual_uncheck:
            for item in uncompleted:
                item['checked'] = True
                self.tree.set(item['id'], "chk", "☑")
            self._update_chk_header_state()

        self.is_running = True
        self._batch_used_outputs = set()
        self.batch_errors = []
        self.btn_start.config(state="disabled")
        self.btn_cancel.config(state="normal")
        self.total_saved_bytes = 0
        self.start_time = time.time()

        self.total_batch_duration = sum(item['duration'] for item in self.file_list if item['status'] != "완료" and item.get('checked', False))
        self.completed_batch_duration = 0

        # [v4.60 fix] 백그라운드 스레드에서 Tkinter 위젯에 직접 접근하면 데드락 발생 가능.
        # 모든 GUI 설정값을 메인 스레드에서 미리 캡처하여 스레드에 전달한다.
        _a = getattr(self, 'combo_audio', None)
        _audio_val = _a.get() if _a else "원본 유지 (기본값)"
        gui_snapshot = {
            'merge_mode': self.merge_mode.get(),
            'merge_fit': self.combo_merge_fit.get() if hasattr(self, 'combo_merge_fit') and self.combo_merge_fit else "",
            'combo_res': self.combo_res.get() if hasattr(self, 'combo_res') else "원본 유지",
            'combo_fps': self.combo_fps.get() if hasattr(self, 'combo_fps') else "원본 유지",
            'combo_hw': self.combo_hw.get() if hasattr(self, 'combo_hw') else "CPU 전용 (호환성 최상)",
            'combo_format': self.combo_format.get() if hasattr(self, 'combo_format') else "MP4 (.mp4)",
            'combo_codec': self.combo_codec.get() if hasattr(self, 'combo_codec') else "",
            'crf': self.crf_var.get() if hasattr(self, 'crf_var') else 28,
            # [v4.60 fix] 추가: 오디오/출력 관련 GUI 값 (백그라운드 스레드 deadlock 방지)
            'combo_audio': _audio_val,
            'audio_copy': "원본" in _audio_val and "음소거" not in _audio_val,
            # [v4.646] 음소거 모드 지원: _audio_val 원문을 그대로 전달하여 판별 가능하게
            'audio_bitrate': (
                "음소거" if "음소거" in _audio_val
                else ("192k" if "192" in _audio_val
                      else ("96k" if "96" in _audio_val
                            else "128k"))
            ),
            'output_mode': self.output_mode.get() if hasattr(self, 'output_mode') else "source",
            'output_dir': self.output_dir if hasattr(self, 'output_dir') else "",
            'filename_mode': self.filename_mode_var.get() if hasattr(self, 'filename_mode_var') else '기존 파일명+인코딩 정보',
            'keep_orig_name': '유지' in (self.filename_mode_var.get() if hasattr(self, 'filename_mode_var') else ''),
            'delete_orig_file': self.delete_orig_file.get() if hasattr(self, 'delete_orig_file') else False,
            'skip_info_file': self.skip_info_file.get() if hasattr(self, 'skip_info_file') else False,
            'photo_option_var': self.photo_option_var.get() if hasattr(self, 'photo_option_var') else "",
            'merge_caption_mode': self.merge_caption_mode.get() if hasattr(self, 'merge_caption_mode') else False,
            'caption_duration_var': self.caption_duration_var.get() if hasattr(self, 'caption_duration_var') else '표시 안함',
            'caption_custom_sec': self.caption_custom_sec.get() if hasattr(self, 'caption_custom_sec') else '5',
            'caption_theme_var': self.caption_theme_var.get() if hasattr(self, 'caption_theme_var') else "🤍 미니멀 글래스 (기본값)",
        }

        threading.Thread(target=self.process_queue_thread, args=(gui_snapshot,), daemon=True).start()

    def process_queue_thread(self, gui_snapshot=None):
        # [v4.60 fix] gui_snapshot이 없으면 빈 dict 사용 (하위 호환)
        if gui_snapshot is None:
            gui_snapshot = {}
        # [v4.60] 비디오 병합 모드 처리 (GUI 위젯 접근 없이 snapshot 사용)
        if gui_snapshot.get('merge_mode', False):
            checked_items = [item for item in self.file_list if item.get('checked', False) and item['status'] != "완료"]
            if not checked_items and self.file_list:
                # 대기열에 항목은 있으나 체크된 항목이 없는 경우 자동으로 전체 대기 항목 체크
                for item in self.file_list:
                    if item['status'] != "완료":
                        item['checked'] = True
                        # [v4.60 fix] 백그라운드 스레드에서 tree.set 직접 호출 → after(0) 사용
                        self.root.after(0, self.tree.set, item['id'], "chk", "☑")
                checked_items = [item for item in self.file_list if item.get('checked', False) and item['status'] != "완료"]
                # self.update_summary() 제거 (존재하지 않는 메서드)

            if len(checked_items) >= 2:
                success = False
                try:
                    success = self.run_ffmpeg_merge(checked_items, gui_snapshot)
                except Exception as e:
                    import traceback
                    err = traceback.format_exc()
                    self.root.after(0, lambda m=err: messagebox.showerror(
                        "❌ 병합 실행 오류",
                        f"병합 작업 중 예외가 발생했습니다.\n\n{m}", parent=self.root))
                if self.is_running and success:
                    self.root.after(0, self.finish_batch)
                else:
                    self.is_running = False
                    self.current_process = None
                    self.root.after(0, lambda: (self.btn_start.config(state="normal"), self.btn_cancel.config(state="disabled")))
                return
            elif len(checked_items) == 1:
                self.root.after(0, lambda: messagebox.showinfo("안내", "병합할 체크(☑) 항목이 1개뿐이므로 단일 인코딩으로 진행합니다.", parent=self.root))
            else:
                self.root.after(0, lambda: messagebox.showinfo("안내", "병합할 체크(☑) 항목이 선택되지 않았습니다.", parent=self.root))
                self.is_running = False
                self.root.after(0, lambda: (self.btn_start.config(state="normal"), self.btn_cancel.config(state="disabled")))
                return

        photo_opt = gui_snapshot.get('photo_option_var', '')
        for index, item in enumerate(self.file_list):
            if not self.is_running:
                break
            if item['status'] == "완료" or not item.get('checked', False):
                continue
            # [v4.63] '모션 JPEG만 작업' 선택 시 음성 없는 정지 사진은 제외
            if item.get('is_static_photo', False) and "모션 JPEG" in photo_opt:
                self.root.after(0, self.tree.set, item['id'], "status", "🚫 제외됨 (정지사진)")
                item['status'] = "제외됨"
                continue

            try:
                self.root.after(0, lambda id=item['id']: self.tree.item(id, tags=('processing',)))
                self.root.after(0, self.tree.set, item['id'], "status", "진행 중 (0.0%) - 남은 시간 계산 중...")

                job_start_time = time.time()
                success = self.run_ffmpeg(item, index, job_start_time, gui_snapshot)
                job_elapsed = time.time() - job_start_time

                if success:
                    out_path = item.get('out_path') or self.get_output_path(
                        item['path'], item.get('used_crf'), item, gui_snapshot)
                    new_size = os.path.getsize(out_path) if os.path.exists(out_path) else 0

                    out_info = self.analyze_output_file(out_path)

                    saved = item['orig_size_b'] - new_size
                    if saved > 0:
                        self.total_saved_bytes += saved

                    final_size_info = f"최종: {new_size / (1024**2):.1f} MB"
                    item['final_size_b'] = new_size

                    self.root.after(0, self.tree.set, item['id'], "result_codec", out_info['codec'])
                    self.root.after(0, self.tree.set, item['id'], "result_bitrate", out_info['bitrate'])
                    self.root.after(0, self.tree.set, item['id'], "size_info", final_size_info)

                    # [v4.2] 원본 파일 삭제 옵션 처리 (스레드 안전 gui_snapshot 사용)
                    # [v4.63] 원본 삭제 후 결과 파일을 원본 이름으로 복원 (중복 방지 포함)
                    del_note = ""
                    should_del_orig = gui_snapshot.get('delete_orig_file', False) if gui_snapshot else self.delete_orig_file.get()
                    if should_del_orig and new_size > 0:
                        orig_p = Path(item['path'])
                        del_ok, del_reason = self.safe_delete_original_file(item['path'], out_path)
                        if del_ok and "완료" in del_reason:
                            del_note = " (원본 삭제됨)"
                            # 원본 삭제 성공 후, 결과 파일을 원본 파일 이름(확장자만 변경)으로 교체 시도
                            try:
                                out_p = Path(out_path)
                                desired_name = orig_p.stem + out_p.suffix
                                desired_path = out_p.parent / desired_name
                                if out_p != desired_path:
                                    if desired_path.exists():
                                        # 동일 이름의 다른 파일이 이미 존재하면 번호 부여
                                        n = 2
                                        while desired_path.exists():
                                            desired_path = out_p.parent / f"{orig_p.stem} ({n}){out_p.suffix}"
                                            n += 1
                                    out_p.rename(desired_path)
                                    out_path = str(desired_path)
                                    item['out_path'] = out_path
                            except OSError:
                                pass  # 이름 변경 실패해도 인코딩 결과는 유지
                        elif not del_ok:
                            del_note = " (⚠️ 원본 삭제 실패)"

                    # [v2.3 추가] 결과물이 원본보다 커지면 경고 표시
                    if new_size >= item['orig_size_b'] > 0:
                        grow_pct = (new_size / item['orig_size_b'] - 1) * 100
                        self.root.after(0, self.tree.set, item['id'], "status",
                                        f"⚠️ 완료 (원본보다 {grow_pct:.0f}% 커짐){del_note}")
                        self.root.after(0, lambda id=item['id']: self.tree.item(id, tags=('error',)))
                    else:
                        self.root.after(0, self.tree.set, item['id'], "status", f"✅ 작업 완료{del_note}")
                        self.root.after(0, lambda id=item['id']: self.tree.item(id, tags=('done',)))
                    item['status'] = "완료"

                    self.completed_batch_duration += item['duration']
                    self.root.after(0, self.update_estimations)

                    # [v4.60 fix] generate_report 호출 시 안전하게 job_elapsed 및 gui_snapshot 전달
                    self.generate_report(item, out_path, new_size, out_info, job_elapsed, saved, gui_snapshot)
                else:
                    self.root.after(0, self.tree.set, item['id'], "status", "❌ 오류 발생 (로그 확인)")
                    self.root.after(0, lambda id=item['id']: self.tree.item(id, tags=('error',)))
                    item['status'] = "오류"
                    self.root.after(0, self.update_estimations)
            except Exception as batch_item_err:
                print(f"[배치 오류] 파일 '{item.get('name')}' 인코딩 처리 중 예외 발생: {batch_item_err}")
                import traceback
                traceback.print_exc()
                self.root.after(0, self.tree.set, item['id'], "status", "❌ 오류 발생")
                self.root.after(0, lambda id=item['id']: self.tree.item(id, tags=('error',)))
                item['status'] = "오류"
                self.root.after(0, self.update_estimations)

        if self.is_running:
            self.root.after(0, self.finish_batch)



    def run_ffmpeg_merge(self, checked_items, gui_snapshot=None):
        # [v4.60 fix] gui_snapshot이 없으면 빈 dict 사용 (하위 호환)
        if gui_snapshot is None:
            gui_snapshot = {}
        """[v4.60] 체크된 비디오들을 순서대로 1개의 완성 영상으로 병합 인코딩"""
        if not checked_items:
            return False

        first_item = checked_items[0]
        # [v4.60 fix] GUI 위젯 접근 없이 snapshot crf를 직접 사용
        # (estimate_file_params -> combo_codec.get()/combo_res.get() 등 GUI 접근 전면 방지)
        snap_crf = gui_snapshot.get('crf', 28)
        mode = first_item.get('crf_mode', 'global')
        if isinstance(mode, int):
            eff_crf = max(0, min(63, mode))
        elif isinstance(mode, str) and mode.startswith('selected_file_'):
            try:
                eff_crf = int(mode.rsplit('_', 1)[-1])
            except ValueError:
                eff_crf = snap_crf
        else:
            # global / auto_q 등 모든 모드: snapshot crf 값을 직접 사용
            eff_crf = snap_crf

        # 1. 출력 파일 경로 결정
        in_path = Path(first_item['path'])
        # [v4.60 fix] get_item_codec() 대신 snapshot 사용 (combo_codec.get() 직접 접근 방지)
        _item_codec_mode = first_item.get('codec_mode', 'global')
        codec_choice = (_item_codec_mode if (_item_codec_mode and _item_codec_mode != 'global')
                        else gui_snapshot.get('combo_codec', ''))

        if "MP3" in codec_choice:
            codec_str = "MP3"
            ext = ".mp3"
        elif "MKV" in codec_choice:
            codec_str = "MKV_HEVC"
            ext = ".mkv"
        elif "H.265" in codec_choice:
            codec_str = "HEVC"
            ext = ".mp4"
        elif "AV1" in codec_choice:
            codec_str = "AV1"
            ext = ".mp4"
        elif "VP9" in codec_choice:
            codec_str = "VP9"
            ext = ".mp4"
        else:
            codec_str = "H264"
            ext = ".mp4"

        # [v4.60 fix] gui_snapshot 사용 (백그라운드 스레드에서 위젯 .get() 금지)
        fmt_choice = gui_snapshot.get('combo_format', '')
        if fmt_choice and "MP3" not in codec_choice:
            ext = ".mkv" if "MKV" in fmt_choice else ".mp4"

        # [v4.60 fix] get_target_dir() 대신 snapshot 사용 (output_mode.get() 직접 접근 방지)
        _out_mode = gui_snapshot.get('output_mode', 'source')
        _out_dir = gui_snapshot.get('output_dir', '')
        if _out_mode == 'custom' and _out_dir:
            target_dir = Path(_out_dir)
            if first_item.get('src_root'):
                parts = [self.sanitize_component(Path(first_item['src_root']).name)]
                rel_dir = first_item.get('rel_dir', '')
                if rel_dir:
                    parts.extend(self.sanitize_component(p) for p in Path(rel_dir).parts if p not in ('.', '..'))
                target_dir = Path(_out_dir).joinpath(*parts)
        elif _out_mode == 'subfolder':
            target_dir = in_path.parent / "압축_결과"
        else:
            target_dir = in_path.parent
        count = len(checked_items)
        base_name = f"[병합] {in_path.stem}_외{count-1}개_{codec_str}_CRF{eff_crf}{ext}" if count > 1 else f"[병합] {in_path.stem}_{codec_str}_CRF{eff_crf}{ext}"
        out_file = str(Path(target_dir) / self.sanitize_component(base_name))

        try:
            out_path_obj = Path(out_file)
            out_path_obj.parent.mkdir(parents=True, exist_ok=True)
            out_file = str(self._uniquify_output(out_path_obj))
        except OSError as e:
            print(f"병합 출력 폴더 생성 실패: {e}")
            return False

        # 2. 규격(해상도, FPS) 결정 (gui_snapshot 사용)
        res_choice = gui_snapshot.get('combo_res', '원본 유지')
        tw, th, _, _ = self.parse_resolution_setting(
            res_choice,
            first_item.get('orig_width') or 1920,
            first_item.get('orig_height') or 1080
        )
        if not tw:
            tw = first_item.get('orig_width') or 1920
        if not th:
            th = first_item.get('orig_height') or 1080

        fps_choice = gui_snapshot.get('combo_fps', '원본 유지')
        if fps_choice != "원본 유지" and fps_choice.isdigit():
            target_fps = int(fps_choice)
        else:
            target_fps = 30

        # 3. FFmpeg 명령어 작성 (선택한 화면 맞춤 모드 반영)
        fit_choice = gui_snapshot.get('merge_fit', '')

        def build_full_cmd(force_cpu=False):
            v_args = self.build_video_encode_args(eff_crf, item, gui_snapshot, force_cpu=force_cpu)
            hw_input_args = []
            if '__HW_INPUT__' in v_args:
                idx = v_args.index('__HW_INPUT__')
                hw_input_args = v_args[idx+1:idx+4]
                v_args = v_args[:idx] + v_args[idx+4:]

            if is_mkv:
                if item.get('is_static_photo', False) and not item.get('motion_mp4_path'):
                    dur = item.get('duration', 3.0)
                    cmd = [self.ffmpeg_path, '-y'] + hw_input_args + ['-loop', '1', '-t', str(dur), '-i', in_file, '-map_metadata', '0']
                else:
                    cmd = [self.ffmpeg_path, '-y'] + hw_input_args + ['-i', in_file, '-map_metadata', '0']
                cmd.extend(v_args)
                cmd.extend(['-map', '0:v:0', '-map', '0:a?', '-map', '0:s?'])
                cmd.extend(self.build_audio_args(item, ".mkv", gui_snapshot))
                cmd.extend(['-c:s', 'copy'])
                cmd.extend(['-f', 'matroska'])
            else:
                common_meta = [
                    '-map_metadata', '0',
                    '-map', '0:v:0', '-map', '0:a:0?', '-map', '0:d?',
                    '-metadata:s:v:0', 'handler_name=VideoHandler',
                    '-metadata:s:a:0', 'handler_name=SoundHandler',
                ]
                if item.get('is_static_photo', False) and not item.get('motion_mp4_path'):
                    dur = item.get('duration', 3.0)
                    cmd = [self.ffmpeg_path, '-y'] + hw_input_args + ['-loop', '1', '-t', str(dur), '-i', in_file] + common_meta + ['-movflags', '+faststart+use_metadata_tags']
                else:
                    cmd = [self.ffmpeg_path, '-y'] + hw_input_args + ['-i', in_file] + common_meta + ['-movflags', '+faststart+use_metadata_tags']
                cmd.extend(v_args)
                cmd.extend(self.build_audio_args(item, ext, gui_snapshot))
                if ext in [".mp4", ".mov", ".m4v"]:
                    cmd.extend(['-f', 'mp4'])

            cmd.append(encode_target)
            return cmd, hw_input_args

        # ... logic continues merging fit logic ...
            if "자동 맞춤" in fit_choice or "Contain" in fit_choice:
                scale_f = f"scale={tw}:{th}:force_original_aspect_ratio=decrease,pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={target_fps},format=yuv420p"
            elif "꽉 채우기" in fit_choice or "Cover" in fit_choice:
                scale_f = f"scale={tw}:{th}:force_original_aspect_ratio=increase,crop={tw}:{th},setsar=1,fps={target_fps},format=yuv420p"
            elif "가운데 정렬" in fit_choice or "Center" in fit_choice:
                scale_f = f"crop='min(iw,{tw})':'min(ih,{th})',pad={tw}:{th}:({tw}-iw)/2:({th}-ih)/2,setsar=1,fps={target_fps},format=yuv420p"
            else:
                scale_f = f"scale={tw}:{th},setsar=1,fps={target_fps},format=yuv420p"

            if is_merge_caption and cap_dur_mode != '표시 안함':
                stem = Path(item['path']).stem
                if '계속' in cap_dur_mode:
                    cap_sec = 9999.0
                else:
                    try:
                        cap_sec = float(gui_snapshot.get('caption_custom_sec', '5'))
                    except (ValueError, TypeError):
                        cap_sec = 5.0
                cap_f = self.build_caption_drawtext_filter(stem, duration=cap_sec, theme_name=caption_theme)
                vfilter = f"[{i}:v]{rot_prefix}{scale_f},{cap_f}[v{i}];"
            else:
                vfilter = f"[{i}:v]{rot_prefix}{scale_f}[v{i}];"

            filter_parts.append(vfilter)

            if not is_mute_mode:
                # [v4.64d] 완벽한 오디오 동기화: 유음/무음 스트림 샘플레이트(44100Hz) 및 스테레오 채널 레이아웃 강제 통일
                has_aud = item.get('_real_has_audio', False)
                dur = item.get('_real_duration') or item.get('duration') or 3.0
                if has_aud:
                    filter_parts.append(f"[{i}:a]aresample=44100:async=1:first_pts=0,aformat=sample_rates=44100:channel_layouts=stereo[a{i}];")
                else:
                    filter_parts.append(f"anullsrc=r=44100:cl=stereo:d={dur:.3f},aresample=44100:async=1,aformat=sample_rates=44100:channel_layouts=stereo[a{i}];")
                concat_inputs += f"[v{i}][a{i}]"
            else:
                concat_inputs += f"[v{i}]"

        if is_mute_mode:
            # 음소거 모드: 오디오 concat 제외, 비디오만 concat
            filter_parts.append(f"{concat_inputs}concat=n={len(checked_items)}:v=1:a=0[outv]")
            filter_complex_str = "".join(filter_parts)
            cmd.extend(['-filter_complex', filter_complex_str, '-map', '[outv]'])
        else:
            filter_parts.append(f"{concat_inputs}concat=n={len(checked_items)}:v=1:a=1[outv][outa]")
            filter_complex_str = "".join(filter_parts)
            cmd.extend(['-filter_complex', filter_complex_str,
                        '-map', '[outv]', '-map', '[outa]'])

        # [v4.60 fix] get_item_codec 대신 snapshot 사용 (코덱 패밀리 결정)
        codec_for_family = gui_snapshot.get('combo_codec', '')
        if "AV1" in codec_for_family:
            family = 'av1'
        elif "H.265" in codec_for_family or "MKV" in codec_for_family:
            family = 'hevc'
        elif "VP9" in codec_for_family:
            family = 'vp9'
        else:
            family = 'h264'

        crf_str = str(eff_crf)
        qp_av1 = str(max(1, min(255, eff_crf * 4)))

        table = {
            'hevc': {
                'AMD': ('hevc_amf', ['-quality', 'quality', '-rc', 'cqp', '-qp_i', crf_str, '-qp_p', crf_str]),
                'NVIDIA': ('hevc_nvenc', ['-preset', 'p6', '-cq', crf_str, '-spatial-aq', '1', '-temporal-aq', '1']),
                'Intel': ('hevc_qsv', ['-preset', 'medium', '-global_quality', crf_str, '-look_ahead', '1']),
                'CPU': ('libx265', ['-crf', crf_str, '-preset', 'medium']),
            },
            'av1': {
                'AMD': ('av1_amf', ['-quality', 'quality', '-rc', 'cqp', '-qp_i', qp_av1, '-qp_p', qp_av1]),
                'NVIDIA': ('av1_nvenc', ['-preset', 'p6', '-cq', crf_str, '-spatial-aq', '1', '-temporal-aq', '1']),
                'Intel': ('av1_qsv', ['-preset', 'medium', '-global_quality', crf_str, '-look_ahead', '1']),
                # [v4.60 최적화] SVT-AV1 고속 인코딩 및 디코딩 재생 호환성 최적화
                'CPU': ('libsvtav1', ['-crf', crf_str, '-preset', '6', '-svtav1-params', 'fast-decode=1']),
            },
            'vp9': {
                'CPU': ('libvpx-vp9', ['-crf', crf_str, '-b:v', '0', '-row-mt', '1', '-tile-columns', '2']),
            },
            'h264': {
                'AMD': ('h264_amf', ['-quality', 'quality', '-rc', 'cqp', '-qp_i', crf_str, '-qp_p', crf_str]),
                'NVIDIA': ('h264_nvenc', ['-preset', 'p6', '-cq', crf_str, '-spatial-aq', '1', '-temporal-aq', '1']),
                'Intel': ('h264_qsv', ['-preset', 'medium', '-global_quality', crf_str]),
                'CPU': ('libx264', ['-crf', crf_str, '-preset', 'medium']),
            },
        }[family]

        cpu_encoder, cpu_args = table['CPU']
        hw = gui_snapshot.get('combo_hw', 'CPU 전용 (호환성 최상)')
        vendor = 'AMD' if 'AMD' in hw else ('NVIDIA' if 'NVIDIA' in hw else ('Intel' if 'Intel' in hw else None))
        if vendor and vendor in table:
            hw_encoder, hw_args = table[vendor]
            encoder, q_args = self.resolve_encoder(hw_encoder, hw_args, cpu_encoder, cpu_args)
        else:
            encoder, q_args = cpu_encoder, cpu_args

        cmd.extend(['-c:v', encoder] + q_args)

        # [v4.64d] 음소거 모드 및 오디오 인코딩 파라미터 보정
        abits = gui_snapshot.get('audio_bitrate', '128k') or '128k'
        if '음소거' in abits or 'mute' in abits.lower() or abits == 'none':
            cmd.extend(['-an'])
        else:
            if not abits or abits in ('원본 (변환 없음)', '원본 복사 (Copy)'):
                abits = '128k'
            cmd.extend(['-c:a', 'aac', '-b:a', abits, '-ar', '44100', '-ac', '2'])
        # [v4.65k FIX] 윈도우 탐색기 '자세히' 탭에서 비디오/오디오 정보가 표시되지 않는 문제 해결
        # - +faststart: moov atom을 파일 앞으로 이동
        # [v4.67b] 자막 통합 및 재생 시각 보정 (Shift)
        merged_sub_entries = []
        acc_offset_sub = 0.0
        temp_sub_root = tempfile.mkdtemp(prefix="svc_merge_sub_")

        for idx_s, item_s in enumerate(checked_items):
            dur_s = item_s.get('_real_duration') or item_s.get('duration') or 3.0
            entries_s = self.extract_or_read_srt(item_s, temp_sub_root, idx_s)
            for s_start, s_end, txt_s in entries_s:
                merged_sub_entries.append((s_start + acc_offset_sub, s_end + acc_offset_sub, txt_s))
            acc_offset_sub += dur_s

        merged_srt_path = None
        if merged_sub_entries:
            merged_sub_entries.sort(key=lambda x: x[0])
            merged_srt_path = os.path.join(temp_sub_root, "merged_subtitles.srt")
            try:
                with open(merged_srt_path, 'w', encoding='utf-8') as f:
                    for idx_m, (st, et, txt_m) in enumerate(merged_sub_entries, 1):
                        f.write(f"{idx_m}\n{self.format_srt_time(st)} --> {self.format_srt_time(et)}\n{txt_m}\n\n")
            except Exception as ex_sub:
                print(f"통합 자막 생성 실패: {ex_sub}")
                merged_srt_path = None

        if ext == ".mp4":
            sub_args = []
            if merged_srt_path:
                sub_args = ['-i', merged_srt_path, '-map', f"{len(checked_items)}:s?",
                            '-metadata:s:s:0', 'language=kor', '-metadata:s:s:0', 'title=한국어',
                            '-metadata:s:s:0', 'handler_name=Korean Subtitle', '-c:s', 'mov_text']
            cmd.extend([
                '-map_metadata', '0',
                '-map', '0:v:0', '-map', '0:a:0?', '-map', '0:d?'
            ] + sub_args + [
                '-movflags', '+faststart+use_metadata_tags',
                '-metadata:s:v:0', 'handler_name=VideoHandler',
                '-metadata:s:a:0', 'handler_name=SoundHandler',
                '-f', 'mp4'
            ])
        elif ext == ".mkv":
            sub_args = []
            if merged_srt_path:
                sub_args = ['-i', merged_srt_path, '-map', f"{len(checked_items)}:s?",
                            '-metadata:s:s:0', 'language=kor', '-metadata:s:s:0', 'title=한국어',
                            '-metadata:s:s:0', 'handler_name=Korean Subtitle', '-c:s', 'subrip']
            cmd.extend([
                '-map_metadata', '0',
                '-map', '0:v:0', '-map', '0:a:0?', '-map', '0:d?'
            ] + sub_args + [
                '-metadata:s:v:0', 'handler_name=VideoHandler',
                '-metadata:s:a:0', 'handler_name=SoundHandler',
                '-f', 'matroska'
            ])
        else:
            sub_args = []
            if merged_srt_path:
                sub_args = ['-i', merged_srt_path, '-map', f"{len(checked_items)}:s?",
                            '-metadata:s:s:0', 'language=kor', '-metadata:s:s:0', 'title=한국어',
                            '-metadata:s:s:0', 'handler_name=Korean Subtitle', '-c:s', 'subrip']
            cmd.extend([
                '-map_metadata', '0',
                '-map', '0:v:0', '-map', '0:a:0?', '-map', '0:d?'
            ] + sub_args + [
                '-metadata:s:v:0', 'handler_name=VideoHandler',
                '-metadata:s:a:0', 'handler_name=SoundHandler',
                '-f', 'matroska'
            ])

        cmd.append(out_file)

        creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0

        # [v4.650] 각 파일별 병합 타임라인 구간(시작 시간 ~ 종료 시간) 계산
        acc_time = 0.0
        for idx, it in enumerate(checked_items):
            dur = it.get('_real_duration') or it.get('duration') or 3.0
            it['_merge_start_time'] = acc_time
            it['_merge_end_time'] = acc_time + dur
            it['_merge_status_cache'] = ''
            acc_time += dur

            # 초기 상태 지정: 첫번째 파일은 처리 중, 이후 파일은 순차 대기
            if idx == 0:
                self.root.after(0, lambda id=it['id']: self.tree.item(id, tags=('processing',)))
                self.root.after(0, self.tree.set, it['id'], "status", "🔗 병합 처리 중 (0%)")
            else:
                self.root.after(0, self.tree.set, it['id'], "status", "⏳ 병합 대기 중")

        total_duration = acc_time if acc_time > 0 else sum(it.get('duration', 0) for it in checked_items)
        job_start_time = time.time()

        try:
            self.last_ffmpeg_cmd = " ".join(cmd)
            self.current_process = subprocess.Popen(
                cmd, stderr=subprocess.PIPE, universal_newlines=True,
                encoding='utf-8', errors='replace', creationflags=creationflags
            )

            time_regex = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")
            last_error_lines = []

            for line in self.current_process.stderr:
                if not self.is_running:
                    break
                line_str = line.strip()
                if line_str:
                    last_error_lines.append(line_str)
                    if len(last_error_lines) > 100:
                        last_error_lines.pop(0)

                match = time_regex.search(line)
                if match and total_duration > 0:
                    h, m, s = match.groups()
                    current_secs = (int(h) * 3600) + (int(m) * 60) + float(s)
                    pct = (current_secs / total_duration) * 100
                    elapsed = time.time() - job_start_time
                    eta = (elapsed / (pct / 100) - elapsed) if pct > 0.5 else 0

                    def _update_merge_main_ui(p_val, text_str):
                        try:
                            self.progress.config(value=p_val)
                            self.lbl_stats.config(text=text_str)
                        except Exception:
                            pass

                    def _update_merge_item_done(i_id, item_dur=0.0):
                        try:
                            self.tree.item(i_id, tags=('done',))
                            self.tree.set(i_id, "status", "✅ 완료 (병합)")
                            self.tree.set(i_id, "eta", "-")
                            if item_dur > 0:
                                self.completed_batch_duration += item_dur
                                self.update_estimations()
                        except Exception:
                            pass

                    def _update_merge_item_proc(i_id, s_str):
                        try:
                            self.tree.item(i_id, tags=('processing',))
                            self.tree.set(i_id, "status", s_str)
                        except Exception:
                            pass

                    lbl_txt = f"🔗 {len(checked_items)}개 파일 병합 중... ({pct:.1f}%) | 남은 시간: {int(eta//60)}분 {int(eta%60)}초"
                    self.root.after(0, _update_merge_main_ui, pct, lbl_txt)

                    # [v4.655] 실시간 각 파일별 작업 완료 및 진행률 상태 Treeview & 대시보드 즉시 순차 반영
                    for it in checked_items:
                        st = it.get('_merge_start_time', 0.0)
                        et = it.get('_merge_end_time', 0.0)
                        item_id = it['id']
                        curr_status = it.get('_merge_status_cache', '')
                        item_dur = max(0.1, et - st)

                        if current_secs >= (et - 0.2) or (it == checked_items[-1] and pct >= 99.0):
                            if curr_status != 'done':
                                it['_merge_status_cache'] = 'done'
                                it['status'] = "완료"
                                self.root.after(0, _update_merge_item_done, item_id, item_dur)
                        elif current_secs > st:
                            # 현재 이 파일 구간이 진행 중
                            file_pct = min(99.0, max(1.0, ((current_secs - st) / item_dur) * 100.0))
                            new_status_str = f"🔗 병합 처리 중 ({file_pct:.0f}%)"
                            if curr_status != new_status_str:
                                it['_merge_status_cache'] = new_status_str
                                self.root.after(0, _update_merge_item_proc, item_id, new_status_str)
                        elif st == 0.0 and current_secs == 0.0 and it == checked_items[0] and curr_status == '':
                            # 아직 time= 파싱 전이지만 첫 파일은 처리 시작된 상태 표시
                            new_status_str = "🔗 병합 처리 중 (0%)"
                            if curr_status != new_status_str:
                                it['_merge_status_cache'] = new_status_str
                                self.root.after(0, _update_merge_item_proc, item_id, new_status_str)

            self.current_process.wait()
            self.last_ffmpeg_returncode = self.current_process.returncode
            
            # SVT 설정 정보를 제외한 핵심 에러 메시지 추출 (생략 방지)
            rel_err_lines = [l for l in last_error_lines if not l.startswith("Svt[info]: SVT [config]")]
            err_msg_clean = "\n".join(rel_err_lines) if rel_err_lines else "\n".join(last_error_lines)
            self.last_ffmpeg_stderr = err_msg_clean if err_msg_clean else "성공 (오류 없음)"

            if self.is_running and self.current_process.returncode == 0:
                new_size = os.path.getsize(out_file) if os.path.exists(out_file) else 0
                out_info = self.analyze_output_file(out_file)
                final_size_info = f"병합완료: {new_size / (1024**2):.1f} MB"

                # [v4.65g] 맨 처음 파일 기준 원본 생성시각 및 수정시각 복사 (파일 정보 유지 모드일 때만)
                f_mode = gui_snapshot.get('filename_mode', '') if gui_snapshot else (getattr(self, 'filename_mode_var', None) and self.filename_mode_var.get() or '')
                if checked_items and os.path.exists(out_file) and '정보 유지' in f_mode:
                    first_src = checked_items[0]['path']
                    self.copy_file_timestamps(first_src, out_file)

                # [v4.67d] '영상과 자막 분리' 모드일 때 병합 통합 자막 .srt 파일도 동일 폴더에 분리 저장
                if self.is_running and os.path.exists(out_file) and merged_srt_path and os.path.exists(merged_srt_path):
                    if '자막 분리' in f_mode or '자막분리' in f_mode:
                        try:
                            srt_out_path = Path(out_file).with_suffix('.srt')
                            shutil.copyfile(merged_srt_path, srt_out_path)
                            print(f"병합 자막 분리 저장 완료: {srt_out_path}")
                        except Exception as ex_m:
                            print(f"병합 자막 분리 저장 실패: {ex_m}")

                def _safe_update_merge_success():
                    try:
                        total_merged_dur = sum(it.get('duration', 0) for it in checked_items)
                        for it in checked_items:
                            it['status'] = "완료"
                            it['out_path'] = out_file
                            try:
                                self.tree.item(it['id'], tags=('done',))
                            except Exception:
                                pass
                            try:
                                self.tree.set(it['id'], "status", "✅ 완료 (병합)")
                                self.tree.set(it['id'], "result_codec", out_info['codec'])
                                self.tree.set(it['id'], "result_bitrate", out_info['bitrate'])
                                self.tree.set(it['id'], "size_info", final_size_info)
                            except Exception:
                                pass
                        self.completed_batch_duration += total_merged_dur
                        self.update_estimations()
                        # [v4.64b] 병합 완료 팝업 제거 → finish_batch의 통합 완료 팝업에서 일괄 처리
                        # 병합 결과 파일 경로를 인스턴스 변수에 저장 (finish_batch에서 사용)
                        self._last_merge_out_file = out_file
                        self._last_merge_count = len(checked_items)
                    except Exception as ex:
                        print(f"병합 완료 GUI 갱신 중 예외: {ex}")

                self.root.after(0, _safe_update_merge_success)
                return True
            else:
                err_msg = err_msg_clean
                print(f"FFmpeg Merge Error:\n{err_msg}")
                for it in checked_items:
                    self.root.after(0, self.tree.set, it['id'], "status", "오류 발생")
                self.root.after(0, lambda msg=err_msg, cmd_str=self.last_ffmpeg_cmd, items=checked_items:
                    self.show_ffmpeg_error_dialog("병합 인코딩 오류 발생", msg, ffmpeg_cmd=cmd_str, checked_items=items)
                )
                return False
        except Exception as e:
            print(f"FFmpeg Merge Exception: {e}")
            err_txt = str(e)
            for it in checked_items:
                self.root.after(0, self.tree.set, it['id'], "status", "오류 발생")
            self.root.after(0, lambda msg=err_txt: messagebox.showerror(
                "❌ 병합 실행 오류",
                f"FFmpeg 병합 작업을 시작하는 중 예외가 발생했습니다.\n\n{msg}", parent=self.root))
            return False
        finally:
            # [v4.63] filter_complex_script 임시 파일 정리
            if hasattr(self, '_merge_filter_tmp') and self._merge_filter_tmp:
                try:
                    os.unlink(self._merge_filter_tmp.name)
                except OSError:
                    pass
                self._merge_filter_tmp = None

    def safe_delete_original_file(self, orig_path, out_path):
        """[v4.2] 작업 완료 후 안전하게 원본 파일을 삭제한다.

        가상 경로(Virtual Path/Network Share/Junction), 파일 잠금(FFmpeg/백신),
        읽기 전용 속성에 대응하는 복합 해제/재시도 알고리즘을 적용한다.
        """
        if not orig_path or not os.path.exists(orig_path):
            return True, "이미 없음"

        # 안전장치: 결과물과 원본 경로가 동일하면 삭제를 건너뜀 (이미 원본이 덮어씌워짐)
        try:
            if Path(orig_path).resolve() == Path(out_path).resolve():
                return True, "결과물과 동일 경로 (덮어씌움)"
        except Exception:
            pass

        # 1단계: 읽기 전용 속성 해제
        try:
            import stat
            os.chmod(orig_path, stat.S_IWRITE | stat.S_IREAD)
        except Exception:
            pass

        # 2단계: 파일 핸들 잔여 정리 (GC)
        import gc
        gc.collect()

        # 3단계: 재시도 루프 (최대 5회)
        for _ in range(5):
            try:
                os.remove(orig_path)
                if not os.path.exists(orig_path):
                    return True, "삭제 완료"
            except OSError:
                pass
            time.sleep(0.2)
            gc.collect()

        # 4단계: Windows CMD 강제 삭제 시도 (가상 경로/네트워크/MTP 연결 등 대응)
        if os.name == 'nt':
            try:
                creationflags = subprocess.CREATE_NO_WINDOW
                subprocess.run(
                    f'cmd /c del /f /q /a "{orig_path}"',
                    shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=creationflags, timeout=3
                )
                if not os.path.exists(orig_path):
                    return True, "CMD 삭제 완료"
            except Exception:
                pass

        # 최종 확인
        if not os.path.exists(orig_path):
            return True, "삭제 완료"

        return False, "파일 잠금 또는 권한 부족"

        self.root.after(0, self.finish_batch)

    def analyze_output_file(self, filepath):
        info_dict = {"codec": "완료", "bitrate": "측정 불가", "width": 0, "height": 0, "raw_bitrate": 0}
        try:
            cmd = [self.ffprobe_path, '-v', 'error', '-select_streams', 'v:0',
                   '-show_entries', 'stream=codec_name,width,height,bit_rate',
                   '-show_entries', 'format=bit_rate', '-of', 'json', filepath]
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, encoding='utf-8', errors='replace',
                                 creationflags=creationflags)
            out_info = json.loads(res.stdout)
            v_stream = out_info.get('streams', [{}])[0]
            fmt = out_info.get('format', {})

            info_dict["codec"] = v_stream.get('codec_name', 'unknown').upper()
            info_dict["width"] = int(v_stream.get('width') or 0)
            info_dict["height"] = int(v_stream.get('height') or 0)

            bitrate = int(v_stream.get('bit_rate') or fmt.get('bit_rate') or 0)
            info_dict["raw_bitrate"] = bitrate
            if bitrate > 0:
                info_dict["bitrate"] = f"{bitrate // 1000:,} kbps"
        except Exception:
            pass
        return info_dict

    def get_full_metadata_str(self, filepath):
        """[v4.65m] ffprobe로 원본 파일의 상세 스트림/포맷 메타데이터 추출."""
        try:
            ffprobe = getattr(self, 'ffprobe_path', None) or 'ffprobe'
            import subprocess as _sp, json as _json
            _flags = _sp.CREATE_NO_WINDOW if __import__('os').name == 'nt' else 0
            cmd = [ffprobe, '-v', 'quiet', '-print_format', 'json',
                   '-show_format', '-show_streams', str(filepath)]
            result = _sp.run(cmd, capture_output=True, text=True,
                             encoding='utf-8', errors='replace',
                             creationflags=_flags, timeout=10)
            if result.returncode != 0:
                return f"  (메타데이터 추출 실패 - ffprobe rc={result.returncode}\n  {result.stderr[:200]})"
            data = _json.loads(result.stdout)
            out = []
            fmt = data.get('format', {})
            # 포맷 전체 정보
            out.append(f"  │ 포맷명    : {fmt.get('format_long_name', fmt.get('format_name', 'N/A'))}")
            duration = float(fmt.get('duration', 0))
            if duration:
                m, s = divmod(int(duration), 60)
                h, m = divmod(m, 60)
                out.append(f"  │ 재생시간  : {h:02d}:{m:02d}:{s:02d} ({duration:.2f}초)")
            bit_rate = fmt.get('bit_rate')
            if bit_rate:
                out.append(f"  │ 전체 비트레이트: {int(bit_rate)//1000} kbps")
            size = fmt.get('size')
            if size:
                sz = int(size)
                out.append(f"  │ 파일 크기  : {sz:,} bytes ({sz/(1024*1024):.1f} MB)")
            # 포맷 태그 (코어 Exif)
            tags = fmt.get('tags', {})
            if tags:
                out.append("  │ [포맷 태그]")
                for k, v in tags.items():
                    out.append(f"  │   {k}: {v}")
            # 스트림 별 정보
            for idx, st in enumerate(data.get('streams', [])):
                stype = st.get('codec_type', 'unknown').upper()
                out.append(f"  ├─ [Stream #{idx} - {stype}]")
                out.append(f"  │   codec      : {st.get('codec_name','N/A')} ({st.get('codec_long_name','')})")
                if stype == 'VIDEO':
                    out.append(f"  │   해상도      : {st.get('width','?')}x{st.get('height','?')}")
                    fps_raw = st.get('r_frame_rate', '')
                    if fps_raw and '/' in fps_raw:
                        n, d = fps_raw.split('/')
                        fps_val = round(int(n)/int(d), 3) if int(d) else 0
                        out.append(f"  │   프레임레이트 : {fps_val} fps")
                    pix_fmt = st.get('pix_fmt')
                    if pix_fmt:
                        out.append(f"  │   픽셀 포맷 : {pix_fmt}")
                    rotation = st.get('tags', {}).get('rotate') or st.get('side_data_list', [{}])[0].get('rotation') if st.get('side_data_list') else None
                    if rotation:
                        out.append(f"  │   회전      : {rotation}도")
                    vbr = st.get('bit_rate')
                    if vbr:
                        out.append(f"  │   비트레이트  : {int(vbr)//1000} kbps")
                elif stype == 'AUDIO':
                    out.append(f"  │   샘플레이트  : {st.get('sample_rate','?')} Hz")
                    out.append(f"  │   채널수    : {st.get('channels','?')} ch ({st.get('channel_layout','')})")
                    abr = st.get('bit_rate')
                    if abr:
                        out.append(f"  │   비트레이트  : {int(abr)//1000} kbps")
                st_tags = st.get('tags', {})
                if st_tags:
                    for k, v in st_tags.items():
                        out.append(f"  │   {k}: {v}")
            return "\n".join(out) if out else "  (정보 없음)"
        except Exception as e:
            return f"  (ffprobe 추출 실패: {e})"

    def generate_report(self, item, out_path_str, new_size, out_info, elapsed, saved_bytes, gui_snapshot=None):
        if gui_snapshot is None:
            gui_snapshot = {}
        if gui_snapshot.get('skip_info_file', False) or (getattr(self, 'skip_info_file', None) and getattr(self.skip_info_file, 'get', lambda: False)()):
            return
        try:
            out_path = Path(out_path_str)
            info_file_path = out_path.with_suffix('.txt')

            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            orig_size = item['orig_size_b']
            saved_pct = (saved_bytes / orig_size) * 100 if orig_size > 0 else 0

            # 해상도 정보
            orig_res = f"{item.get('orig_width', 0)} x {item.get('orig_height', 0)}" if item.get('orig_width') else "원본 해상도"
            out_w = out_info.get('width', 0)
            out_h = out_info.get('height', 0)
            comp_res = f"{out_w} x {out_h}" if out_w > 0 else orig_res

            # 코덱 / 비트레이트 / 용량 정보
            orig_codec = item.get('orig_codec') or 'UNKNOWN'
            comp_codec = out_info.get('codec') or 'UNKNOWN'
            orig_bitrate = item.get('orig_bitrate') or 'N/A'
            comp_bitrate = out_info.get('bitrate') or 'N/A'

            orig_size_str = self.format_size(orig_size)
            comp_size_str = self.format_size(new_size)
            saved_size_str = self.format_size(abs(saved_bytes))

            if saved_bytes > 0:
                change_str = f"▼ {saved_size_str} ({saved_pct:.1f}% 절약)"
            elif saved_bytes < 0:
                change_str = f"▲ {saved_size_str} ({abs(saved_pct):.1f}% 증가)"
            else:
                change_str = "변화 없음 (0%)"

            is_del = gui_snapshot.get('delete_orig_file', False) if gui_snapshot else False
            orig_del_str = "삭제됨 (작업 완료 후 원본 자동 삭제)" if is_del else "원본 보존"
            hw_str = gui_snapshot.get('combo_hw', 'CPU 전용') if gui_snapshot else 'CPU 전용'
            audio_str = gui_snapshot.get('combo_audio', '원본 유지') if gui_snapshot else '원본 유지'
            crf_val = item.get('used_crf', gui_snapshot.get('crf', 28) if gui_snapshot else 28)

            report = f"""================================================================================
                    🎬 스마트 동영상 압축 완료 보고서 ({self.build_version})
================================================================================

[ 📌 기본 작업 정보 ]
 - 작업 일시 : {now}
 - 소요 시간 : {int(elapsed)}초
 - 가속 장치 : {hw_str}
 - 설정 화질 : CRF {crf_val}
 - 오디오 설정: {audio_str}
 - 원본 처리 : {orig_del_str}

--------------------------------------------------------------------------------
 📊 [항목별 전/후 주요 스펙 비교]
--------------------------------------------------------------------------------
 1. 파일 용량 (File Size)
    • 압축 전 (원본)   : {orig_size_str} ({orig_size:,} bytes)
    • 압축 후 (최종)   : {comp_size_str} ({new_size:,} bytes)
    • 용량 절감 효과   : {change_str}

 2. 비디오 코덱 (Video Codec)
    • 압축 전 (원본)   : {orig_codec}
    • 압축 후 (최종)   : {comp_codec} (고효율 인코딩)

 3. 해상도 (Resolution)
    • 압축 전 (원본)   : {orig_res}
    • 압축 후 (최종)   : {comp_res}
    • 변경 사항        : {"해상도 변경 적용됨" if orig_res != comp_res else "원본 해상도 유지"}

 4. 비트레이트 (Bitrate)
    • 압축 전 (원본)   : {orig_bitrate}
    • 압축 후 (최종)   : {comp_bitrate}

 5. 원본 파일 상세 정보 (Exif/Metadata)
{self.get_full_metadata_str(item['path'])}

--------------------------------------------------------------------------------
 📁 [파일 경로 정보]
 - 원본 파일 경로 : {item['path']}
 - 결과 파일 경로 : {str(out_path)}
================================================================================"""

            with open(info_file_path, 'w', encoding='utf-8') as f:
                f.write(report)
        except Exception as e:
            print(f"리포트 생성 실패: {e}")

    def _strip_existing_compression_tag(self, stem):
        """[v4.5] 원본 파일명 끝에 기존 '_코덱_해상도_CRF수치' 패턴이 있으면 제거하여 순수 원본 이름을 추출한다."""
        p1 = r'_(?:HEVC|H264|AV1|VP9|MKV_HEVC|MKV|compressed|압축본)(?:_\d+x\d+)?_CRF\d+$'
        stem = re.sub(p1, '', stem, flags=re.IGNORECASE)
        p2 = r'(?:_(?:HEVC|H264|AV1|VP9|MKV_HEVC|MKV|compressed|압축본))?(?:_\d+x\d+)?_CRF\d+$'
        stem = re.sub(p2, '', stem, flags=re.IGNORECASE)
        p3 = r'_(?:compressed|압축본)$'
        return re.sub(p3, '', stem, flags=re.IGNORECASE)

    def get_output_path(self, in_path_str, crf_val=None, item=None, gui_snapshot=None):
        in_path = Path(in_path_str)

        # 원본 해상도와 저장 위치 계산에 사용할 대기열 항목을 먼저 찾는다.
        if item is None:
            item = next((f for f in self.file_list if f['path'] == str(in_path)), None)

        codec_choice = self.get_item_codec(item)
        if "MP3" in codec_choice:
            codec_str = "MP3"
        elif "MKV" in codec_choice:
            codec_str = "MKV_HEVC"
        elif "H.265" in codec_choice:
            codec_str = "HEVC"
        elif "AV1" in codec_choice:
            codec_str = "AV1"
        elif "VP9" in codec_choice:
            codec_str = "VP9"
        else:
            codec_str = "H264"

        res_choice = self.combo_res.get()
        tw, th, _, _ = self.parse_resolution_setting(res_choice)
        if tw and th:
            res_str = f"{tw}x{th}"
        elif th:
            res_str = f"{th}p"
        else:
            # '원본해상도'라는 문구 대신 해당 파일의 실제 해상도 값을 사용한다.
            width = (item or {}).get('orig_width', 0)
            height = (item or {}).get('orig_height', 0)
            if width and height:
                res_str = f"{width}x{height}"
            else:
                raw_res = str((item or {}).get('orig_res') or '').strip()
                res_str = raw_res if re.fullmatch(r'\d+x\d+', raw_res) else "원본"

        f_mode = self.filename_mode_var.get() if hasattr(self, 'filename_mode_var') else ""
        if gui_snapshot and 'filename_mode' in gui_snapshot:
            f_mode = gui_snapshot['filename_mode']

        if "MP3" in codec_choice:
            ext = ".mp3"
        elif "유지" in f_mode or self.keep_orig_name.get():
            # [v4.65r FIX] '기존 파일명 유지' 선택 시 원본 확장자(orig_ext)를 강제 유지하는 대신, 선택된 출력 포맷(combo_format)을 따르도록 수정
            ext_choice = getattr(self, 'combo_format', None)
            if ext_choice:
                m = re.search(r'\(\.(.+?)\)', ext_choice.get())
                if m:
                    ext = "." + m.group(1).lower()
                else:
                    ext = ".mkv" if "MKV" in ext_choice.get() else ".mp4"
            else:
                ext = in_path.suffix.lower()
        elif "MKV" in codec_choice:
            ext = ".mkv"
        else:
            ext_choice = getattr(self, 'combo_format', None)
            ext = ".mkv" if ext_choice and "MKV" in ext_choice.get() else ".mp4"

        if crf_val is None:
            crf_val = self.crf_var.get()

        target_dir = self.get_target_dir(item, gui_snapshot) or in_path.parent

        if "MP3" in codec_choice:
            out_name = f"{in_path.stem}_MP3{ext}"
        elif "유지" in f_mode or self.keep_orig_name.get():
            out_name = f"{in_path.stem}{ext}"
        else:
            base_stem = self._strip_existing_compression_tag(in_path.stem)
            out_name = f"{base_stem}_{codec_str}_{res_str}_CRF{crf_val}{ext}"

        out_name = self.sanitize_component(out_name)
        full = Path(target_dir) / out_name

        # [v4.67g] 원본 파일 삭제 미선택 시 출력 경로가 원본과 완전히 같아지거나 충돌 시 (1) 자동 번호 부여
        del_orig = gui_snapshot.get('delete_orig_file', False) if gui_snapshot else (hasattr(self, 'delete_orig_file') and self.delete_orig_file.get())
        if not del_orig:
            try:
                if full.resolve() == in_path.resolve():
                    full = self._uniquify_output(full)
            except OSError:
                pass

        full = self._shorten_for_maxpath(full)
        return str(full)

    def run_ffmpeg(self, item, index, job_start_time, gui_snapshot=None):
        if gui_snapshot is None:
            gui_snapshot = {}
        in_file = item['path']
        # [v2.4] 파일별 개별 화질(CRF) 반영 (스레드 안전 gui_snapshot 전달)
        eff_crf = self.get_effective_crf(item, gui_snapshot)
        item['used_crf'] = eff_crf
        out_file = self.get_output_path(in_file, eff_crf, item, gui_snapshot)

        is_keep_name = gui_snapshot.get('keep_orig_name', False) if gui_snapshot else getattr(self.keep_orig_name, 'get', lambda: False)()
        is_del_orig = gui_snapshot.get('delete_orig_file', False) if gui_snapshot else (hasattr(self, 'delete_orig_file') and self.delete_orig_file.get())

        # [v3.0] 하위 폴더 자동 생성 + 출력 파일명 충돌 자동 회피
        try:
            out_path_obj = Path(out_file)
            out_path_obj.parent.mkdir(parents=True, exist_ok=True)
            if not is_keep_name and not is_del_orig:
                out_file = str(self._uniquify_output(out_path_obj))
        except OSError as e:
            print(f"출력 폴더 생성 실패: {e}")
            self.root.after(0, lambda: messagebox.showerror(
                "저장 폴더 오류",
                f"출력 폴더를 만들 수 없습니다.\n{out_file}\n\n{e}\n\n"
                "저장 폴더의 권한이나 경로 길이를 확인해주세요.", parent=self.root))
            return False
        item['out_path'] = out_file   # 완료 처리 시 재계산 없이 그대로 사용

        needs_replace = False
        encode_target = out_file
        if Path(out_file).exists():
            if is_del_orig:
                # [v4.67g] 원본 파일 삭제 체크 시에만 임시 파일에 인코딩 후 원본 교체/삭제
                p_obj = Path(out_file)
                encode_target = str(p_obj.parent / f"{p_obj.stem}_tmp{p_obj.suffix}")
                needs_replace = True
            else:
                # [v4.67g] 원본 파일 삭제 미체크 -> 어떠한 경우에도 원본을 덮어쓰지 않고 (1), (2) 번호 부여하여 안전 보존!
                out_file = str(self._uniquify_output(Path(out_file)))
                item['out_path'] = out_file
                encode_target = out_file

        ext = Path(out_file).suffix.lower()
        codec_choice = self.get_item_codec(item, gui_snapshot)

        # [v4.65a] 원본 파일 확장자 기억 (3GP/구형 컨테이너 안전장치용)
        orig_ext = Path(item['path']).suffix.lower()
        # [v4.65a] 구형 컨테이너(.3gp, .3g2, .flv, .wmv, .asf, .rm, .vob) 원본을 인코딩할 때
        #          출력 확장자가 여전히 구형이면 강제 MP4 전환 (코덱 불일치 인코딩 실패 원천 방지)
        _LEGACY_CONTAINERS = {'.3gp', '.3g2', '.flv', '.wmv', '.asf', '.rm', '.vob', '.divx'}
        if ext in _LEGACY_CONTAINERS and "MP3" not in codec_choice:
            ext = ".mp4"
            out_file = str(Path(out_file).with_suffix(".mp4"))
            encode_target = out_file if not needs_replace else str(Path(encode_target).with_suffix(".mp4"))
            item['out_path'] = out_file
            print(f"[v4.65a] 구형 컨테이너 '{orig_ext}' → '.mp4' 자동 전환: {Path(out_file).name}")

        in_file = item.get('motion_mp4_path') or self.extract_motion_photo_mp4(item['path']) or item['path']
        if "MP3" in codec_choice or ext == ".mp3":
            # MP3 오디오 전용 추출 모드: 비디오 트랙 무시(-vn) + MP3 오디오 인코딩 + 메타데이터/태그 보존
            # [v4.65j FIX] faststart 적용하여 윈도우 탐색기 속성 정상 표시
            cmd = [self.ffmpeg_path, '-y', '-i', in_file, '-map_metadata', '0', '-movflags', '+faststart+use_metadata_tags', '-vn', '-map', '0:a:0?']
            is_copy = gui_snapshot.get('audio_copy', False) if gui_snapshot else self.audio_copy_selected()
            if is_copy:
                cmd.extend(['-c:a', 'copy'])
            else:
                audio_b = gui_snapshot.get('audio_bitrate', '128k') if gui_snapshot else (self.get_audio_encode_bitrate() or '128k')
                if not audio_b or audio_b in ('None', '음소거', None):
                    audio_b = '128k'
                cmd.extend(['-c:a', 'libmp3lame', '-b:a', audio_b])
            cmd.extend(['-f', 'mp3'])
        elif "MKV" in codec_choice or ext == ".mkv":
            # MKV 모드: 원본 Exif/카메라/촬영시각/위치 태그 보존 (-map_metadata 0)
            ext_sub = item.get('ext_sub_file')
            if item.get('is_static_photo', False) and not item.get('motion_mp4_path'):
                dur = item.get('duration', 3.0)
                cmd = [self.ffmpeg_path, '-y', '-loop', '1', '-t', str(dur), '-i', in_file]
            else:
                cmd = [self.ffmpeg_path, '-y', '-i', in_file]

            if ext_sub and os.path.exists(ext_sub):
                cmd.extend(['-i', ext_sub])

            cmd.extend(['-map_metadata', '0'])
            cmd.extend(self.build_video_encode_args(eff_crf, item, gui_snapshot))
            if ext_sub and os.path.exists(ext_sub):
                cmd.extend(['-map', '0:v:0', '-map', '0:a?', '-map', '0:s?', '-map', '1:s?',
                            '-metadata:s:s:0', 'language=kor', '-metadata:s:s:0', 'title=한국어'])
            else:
                cmd.extend(['-map', '0:v:0', '-map', '0:a?', '-map', '0:s?',
                            '-metadata:s:s:0', 'language=kor', '-metadata:s:s:0', 'title=한국어'])
            cmd.extend(self.build_audio_args(item, ".mkv", gui_snapshot))
            cmd.extend(['-c:s', 'copy'])
            cmd.extend(['-f', 'matroska'])
        else:
            # [v4.65k] common_meta: 메타데이터 + 스트림 핸들러명
            # [v4.65n] -map 0:v:0 -map 0:a:0? -map 0:d? : GPS/데이터 스트림까지 보존
            ext_sub = item.get('ext_sub_file')
            has_sub = item.get('has_subtitle', False)
            common_meta = [
                '-map_metadata', '0',
                '-map', '0:v:0', '-map', '0:a:0?', '-map', '0:d?',
                '-metadata:s:v:0', 'handler_name=VideoHandler',
                '-metadata:s:a:0', 'handler_name=SoundHandler',
            ]
            if ext_sub and os.path.exists(ext_sub):
                common_meta.extend(['-map', '1:s?'])
            elif has_sub:
                common_meta.extend(['-map', '0:s?'])

            if item.get('is_static_photo', False) and not item.get('motion_mp4_path'):
                dur = item.get('duration', 3.0)
                cmd = [self.ffmpeg_path, '-y', '-loop', '1', '-t', str(dur), '-i', in_file]
            else:
                cmd = [self.ffmpeg_path, '-y', '-i', in_file]

            if ext_sub and os.path.exists(ext_sub):
                cmd.extend(['-i', ext_sub])

            cmd.extend(common_meta + ['-movflags', '+faststart+use_metadata_tags'])
            cmd.extend(self.build_video_encode_args(eff_crf, item, gui_snapshot))
            cmd.extend(self.build_audio_args(item, ext, gui_snapshot))
            if has_sub or ext_sub:
                cmd.extend(['-metadata:s:s:0', 'language=kor', '-metadata:s:s:0', 'title=한국어',
                            '-metadata:s:s:0', 'handler_name=Korean Subtitle', '-c:s', 'mov_text'])
            if ext in [".mp4", ".mov", ".m4v"]:
                cmd.extend(['-f', 'mp4'])

        cmd.append(encode_target)

        creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0

        try:
            self.last_ffmpeg_cmd = " ".join(str(x) for x in cmd)
            self.current_process = subprocess.Popen(
                cmd, stderr=subprocess.PIPE, universal_newlines=True,
                encoding='utf-8', errors='replace', creationflags=creationflags
            )

            time_regex = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")
            last_error_lines = []

            for line in self.current_process.stderr:
                if not self.is_running:
                    break

                line_str = line.strip()
                if line_str:
                    last_error_lines.append(line_str)
                    if len(last_error_lines) > 100:
                        last_error_lines.pop(0)

                match = time_regex.search(line)
                if match and item['duration'] > 0:
                    h, m, s = match.groups()
                    current_secs = (int(h) * 3600) + (int(m) * 60) + float(s)
                    pct = (current_secs / item['duration']) * 100

                    self.root.after(0, self.update_detailed_progress, item, item['id'],
                                    index, item['name'], pct, job_start_time)

            self.current_process.wait()
            self.last_ffmpeg_returncode = self.current_process.returncode

            rel_err_lines = [l for l in last_error_lines if not l.startswith("Svt[info]: SVT [config]")]
            err_msg_clean = "\n".join(rel_err_lines) if rel_err_lines else "\n".join(last_error_lines)
            self.last_ffmpeg_stderr = err_msg_clean if err_msg_clean else "성공 (오류 없음)"

            if self.is_running and self.current_process.returncode != 0:
                err_msg = err_msg_clean
                print(f"FFmpeg Error:\n{err_msg}")
                if needs_replace and os.path.exists(encode_target):
                    try:
                        os.remove(encode_target)
                    except:
                        pass
                
                # [v4.631e] 개별 오류 팝업 대신 배치 오류 목록에 수집 (작업 완료 후 통합 창 출력)
                cat = self._categorize_ffmpeg_error(err_msg, self.current_process.returncode, item)
                if not hasattr(self, 'batch_errors'):
                    self.batch_errors = []
                self.batch_errors.append({
                    'index': index + 1,
                    'name': item['name'],
                    'path': item['path'],
                    'returncode': self.current_process.returncode,
                    'stderr': err_msg,
                    'category': cat
                })
                return False

            if self.is_running and needs_replace:
                try:
                    os.replace(encode_target, out_file)
                except OSError as e:
                    print(f"파일 덮어쓰기 실패: {e}")
                    return False

            # [v4.67f] 비디오 스트림 유실 감지 및 검증 (음성 전용 MKV/MP4 결손 파일 방지)
            if self.is_running and os.path.exists(out_file) and "MP3" not in codec_choice and ext != ".mp3":
                orig_has_video = (item.get('orig_width', 0) > 0 or item.get('orig_height', 0) > 0 or item.get('orig_codec') not in ('none', 'unknown', ''))
                if orig_has_video:
                    out_probe = self.analyze_output_file(out_file)
                    if out_probe.get('width', 0) == 0 and out_probe.get('height', 0) == 0 and out_probe.get('codec') in ('UNKNOWN', 'NONE', ''):
                        err_msg = "[비디오 스트림 누락 결함] 변환된 출력 파일에 영상 트랙이 생성되지 않고 음성만 존재합니다."
                        print(f"ERROR: {err_msg} -> {out_file}")
                        try:
                            os.remove(out_file)
                        except Exception:
                            pass
                        self.last_ffmpeg_returncode = -2
                        self.last_ffmpeg_stderr = err_msg
                        if not hasattr(self, 'batch_errors'):
                            self.batch_errors = []
                        self.batch_errors.append({
                            'index': index + 1,
                            'name': item['name'],
                            'path': item['path'],
                            'returncode': -2,
                            'stderr': err_msg,
                            'category': "비디오 스트림 생성 실패"
                        })
                        return False

            # [v4.65c FIX / v4.65g] 원본 파일 생성시각 및 수정시각 복사 (파일 정보 유지 모드일 때만)
            f_mode = gui_snapshot.get('filename_mode', '') if gui_snapshot else (getattr(self, 'filename_mode_var', None) and self.filename_mode_var.get() or '')
            if self.is_running and os.path.exists(out_file) and '정보 유지' in f_mode:
                self.copy_file_timestamps(item['path'], out_file)

            # [v4.67d] '영상과 자막 분리' 모드: 자막 포함 시 동일 폴더에 .srt 파일로 자동 추출/분리 저장
            if self.is_running and os.path.exists(out_file) and ('자막 분리' in f_mode or '자막분리' in f_mode):
                try:
                    entries = self.extract_or_read_srt(item, tempfile.gettempdir(), index)
                    if entries:
                        srt_out_path = Path(out_file).with_suffix('.srt')
                        with open(srt_out_path, 'w', encoding='utf-8') as f_sub:
                            for idx_s, (st_s, et_s, txt_s) in enumerate(entries, 1):
                                f_sub.write(f"{idx_s}\n{self.format_srt_time(st_s)} --> {self.format_srt_time(et_s)}\n{txt_s}\n\n")
                        print(f"자막 분리 추출 완료: {srt_out_path}")
                except Exception as ex_ext:
                    print(f"자막 분리 추출 실패: {ex_ext}")

            return self.is_running

        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            self.last_ffmpeg_returncode = -1
            self.last_ffmpeg_stderr = f"[Python Runtime Exception]\n{tb_str}"
            item['status'] = '오류'
            print(f"프로세스 실행 예외: {e}\n{tb_str}")
            if 'needs_replace' in locals() and needs_replace and os.path.exists(encode_target):
                try:
                    os.remove(encode_target)
                except:
                    pass
            return False

    def update_detailed_progress(self, item, item_id, index, name, pct, job_start_time):
        pct = min(max(pct, 0), 100)

        elapsed = time.time() - job_start_time
        elapsed_str = self.format_time(elapsed)
        eta_str = "계산 중..."

        if elapsed > 3 and pct > 0:
            total_est_time = elapsed / (pct / 100)
            rem_sec = int(total_est_time - elapsed)
            eta_str = f"약 {self.format_time(rem_sec)}"

        status_msg = f"진행 중 ({pct:.1f}%) - 소요: {elapsed_str} / 남음: {eta_str}"
        self.tree.set(item_id, "status", status_msg)

        current_processed_duration = self.completed_batch_duration + (item['duration'] * (pct / 100))
        batch_pct = (current_processed_duration / self.total_batch_duration) * 100 if getattr(self, 'total_batch_duration', 0) > 0 else 0
        batch_pct = min(max(batch_pct, 0), 100)

        self.progress['value'] = batch_pct

        total_elapsed = time.time() - self.start_time
        total_elapsed_str = self.format_time(total_elapsed)
        total_eta_str = "계산 중..."

        if total_elapsed > 3 and batch_pct > 0:
            batch_total_est = total_elapsed / (batch_pct / 100)
            batch_rem_sec = int(batch_total_est - total_elapsed)
            total_eta_str = f"약 {self.format_time(batch_rem_sec)}"

        total_files = len(self.file_list)

        dash_text = (f"[전체 {batch_pct:.1f}% | 소요: {total_elapsed_str} | 남음: {total_eta_str}] ➔ "
                     f"[{index+1}/{total_files}] '{name}' 처리중 ({pct:.1f}%) | 개별 소요: {elapsed_str} | 남음: {eta_str}")
        self.lbl_stats.config(text=dash_text)

    def cancel_batch(self):
        self.is_running = False
        if self.current_process:
            self.current_process.terminate()
        self.lbl_stats.config(text="사용자에 의해 작업이 취소되었습니다.")
        self.btn_start.config(state="normal")
        self.btn_cancel.config(state="disabled")
        self.progress['value'] = 0

    def finish_batch(self):
        self.is_running = False
        self.current_process = None
        self.btn_start.config(state="normal")
        self.btn_cancel.config(state="disabled")
        self.progress['value'] = 100

        elapsed = int(time.time() - self.start_time)
        saved_mb = self.total_saved_bytes / (1024**2)
        saved_gb = self.total_saved_bytes / (1024**3)

        save_str = f"{saved_gb:.2f} GB" if saved_gb >= 1 else f"{saved_mb:.1f} MB"
        info_msg = " (.txt 리포트 생성 완료)" if not self.skip_info_file.get() else " (.txt 리포트 생성 생략됨)"

        err_count = len(getattr(self, 'batch_errors', []))
        if err_count > 0:
            msg = f"⚠️ 배치 작업 완료 (소요 시간: {elapsed}초) | 총 {save_str} 절약 | ⚠️ 오류 {err_count}건 발생"
            self.lbl_stats.config(text=msg)
            self.root.after(100, lambda: self.show_batch_error_summary_dialog(elapsed))
        else:
            # [v4.64b] 병합 완료 + 작업 완료 팝업 통합: 병합이 있었으면 저장 파일 정보 함께 표시
            merge_out = getattr(self, '_last_merge_out_file', None)
            merge_cnt = getattr(self, '_last_merge_count', 0)
            if merge_out:
                merge_info = f"\n\n📁 병합 저장 파일:\n{merge_out}\n(총 {merge_cnt}개 → 1개 병합)"
                self._last_merge_out_file = None
                self._last_merge_count = 0
            else:
                merge_info = ""
            msg = f"✅ 모든 작업 완료! (소요 시간: {elapsed}초) | 총 {save_str} 용량 절약{info_msg}{merge_info}"
            self.lbl_stats.config(text=msg.split('\n')[0])
            # [v4.64b] 통합 완료 팝업: 저장위치 열기 / 저장파일 열기 버튼 포함 커스텀 다이얼로그
            self._show_finish_dialog(msg, merge_out)

    def open_last_output_dir(self):
        """[v4.64b] 마지막으로 저장한 출력 폴더를 탐색기로 열기"""
        out_file = getattr(self, '_last_out_file_path', None)
        if not out_file:
            # 대기열의 완료된 항목에서 마지막 경로 검색
            for it in reversed(self.file_list):
                if it.get('out_path') and os.path.exists(it['out_path']):
                    out_file = it['out_path']
                    break
        if out_file and os.path.exists(out_file):
            folder = os.path.dirname(out_file)
            if os.name == 'nt':
                os.startfile(folder)
            else:
                import subprocess as _sp
                _sp.Popen(['xdg-open', folder])
        else:
            # 지정 폴더 또는 원본 폴더
            mode = self.output_mode.get() if hasattr(self, 'output_mode') else 'source'
            folder = self.output_dir if (mode == 'custom' and self.output_dir) else ''
            if not folder:
                # file_list에서 경로 추출 시도
                for it in self.file_list:
                    p = it.get('path', '')
                    if p and os.path.exists(p):
                        folder = os.path.dirname(p)
                        break
            if folder and os.path.exists(folder):
                if os.name == 'nt':
                    os.startfile(folder)
            else:
                AppMessageBox.showinfo("안내", "열 수 있는 저장 폴더를 찾을 수 없습니다.\n먼저 작업을 완료해주십시오.", parent=self.root)

    def open_last_output_file(self):
        """[v4.64b] 마지막으로 저장한 출력 파일을 기본 플레이어로 열기"""
        out_file = getattr(self, '_last_out_file_path', None)
        if not out_file:
            for it in reversed(self.file_list):
                if it.get('out_path') and os.path.exists(it['out_path']):
                    out_file = it['out_path']
                    break
        if out_file and os.path.exists(out_file):
            if os.name == 'nt':
                os.startfile(out_file)
            else:
                import subprocess as _sp
                _sp.Popen(['xdg-open', out_file])
        else:
            AppMessageBox.showinfo("안내", "열 수 있는 저장 파일을 찾을 수 없습니다.\n먼저 작업을 완료해주십시오.", parent=self.root)

    def _show_finish_dialog(self, msg, merge_out_file=None):
        """[v4.64b] 작업 완료 통합 팝업: 저장위치 열기 / 저장파일 열기 버튼 포함"""
        # 마지막 출력 파일 경로 갱신
        if merge_out_file and os.path.exists(merge_out_file):
            self._last_out_file_path = merge_out_file
        else:
            # 대기열에서 마지막 완료 파일 추적
            for it in reversed(self.file_list):
                if it.get('out_path') and os.path.exists(it.get('out_path', '')):
                    self._last_out_file_path = it['out_path']
                    break

        last_file = getattr(self, '_last_out_file_path', None)

        dlg = tk.Toplevel(self.root)
        dlg.title("✅ 작업 완료")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.configure(bg='#1e293b')

        # 상단 아이콘 + 제목
        hdr = tk.Frame(dlg, bg='#1e293b', pady=16)
        hdr.pack(fill='x', padx=20)
        tk.Label(hdr, text="✅ 모든 작업이 완료되었습니다!",
                 font=("Malgun Gothic", 13, "bold"),
                 bg='#1e293b', fg='#22c55e').pack()

        # 메시지 텍스트
        msg_frame = tk.Frame(dlg, bg='#0f172a', padx=14, pady=10)
        msg_frame.pack(fill='both', padx=20, pady=(0, 12))
        msg_lbl = tk.Text(msg_frame, wrap='word', height=8, width=60,
                          bg='#0f172a', fg='#e2e8f0', relief='flat',
                          font=("Malgun Gothic", 9), padx=6, pady=6,
                          state='normal', cursor='arrow')
        msg_lbl.insert('1.0', msg)
        msg_lbl.config(state='disabled')
        msg_lbl.pack(fill='both', expand=True)

        # 버튼 행
        btn_row = tk.Frame(dlg, bg='#1e293b', pady=12)
        btn_row.pack(fill='x', padx=20)

        def _open_dir():
            if last_file and os.path.exists(last_file):
                folder = os.path.dirname(last_file)
            else:
                folder = self.output_dir if (self.output_mode.get() == 'custom' and self.output_dir) else ''
                if not folder:
                    for it in self.file_list:
                        p = it.get('path', '')
                        if p and os.path.exists(p):
                            folder = os.path.dirname(p)
                            break
            if folder and os.path.exists(folder):
                os.startfile(folder) if os.name == 'nt' else None

        def _open_file():
            if last_file and os.path.exists(last_file):
                os.startfile(last_file) if os.name == 'nt' else None

        style_btn = {'font': ('Malgun Gothic', 9, 'bold'), 'relief': 'flat',
                     'padx': 14, 'pady': 6, 'cursor': 'hand2', 'bd': 0}

        tk.Button(btn_row, text="📂 저장위치 열기",
                  bg='#334155', fg='#94a3b8', activebackground='#475569',
                  command=_open_dir, **style_btn).pack(side='left', padx=(0, 8))

        file_btn_state = 'normal' if last_file and os.path.exists(last_file or '') else 'disabled'
        tk.Button(btn_row, text="🎬 저장파일 열기",
                  bg='#166534', fg='#bbf7d0', activebackground='#15803d',
                  state=file_btn_state,
                  command=_open_file, **style_btn).pack(side='left', padx=(0, 8))

        # [v4.65h] 리포트 파일 존재 시 리포트 열기 버튼 표시
        report_file = os.path.splitext(last_file)[0] + '.txt' if last_file else ''
        def _open_report():
            if report_file and os.path.exists(report_file):
                os.startfile(report_file) if os.name == 'nt' else None

        if report_file and os.path.exists(report_file):
            tk.Button(btn_row, text="📄 리포트 열기",
                      bg='#475569', fg='#f8fafc', activebackground='#334155',
                      command=_open_report, **style_btn).pack(side='left', padx=(0, 8))

        tk.Button(btn_row, text="확인",
                  bg='#2563eb', fg='white', activebackground='#1d4ed8',
                  command=dlg.destroy, **style_btn).pack(side='right')

        dlg.update_idletasks()
        # 창 화면 가운데 배치
        w = dlg.winfo_reqwidth()
        h = dlg.winfo_reqheight()
        x = self.root.winfo_x() + (self.root.winfo_width() - w) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - h) // 2
        dlg.geometry(f"+{x}+{y}")
        dlg.wait_window()

    def show_ffmpeg_error_dialog(self, title, error_message, ffmpeg_cmd="", checked_items=None):
        """[v4.641] FFmpeg 인코딩 및 병합 오류 발생 시 상세 로그 및 [📋 클립보드로 전체 오류 내용 복사] 버튼을 제공하는 모달 창"""
        err_dialog = tk.Toplevel(self.root)
        err_dialog.title(f"❌ {title}")
        err_dialog.geometry("860x660")
        err_dialog.minsize(720, 520)
        err_dialog.transient(self.root)
        err_dialog.grab_set()

        # 헤더
        header_frame = ttk.Frame(err_dialog, padding=12)
        header_frame.pack(fill="x")

        title_lbl = ttk.Label(
            header_frame,
            text=f"❌ {title}",
            font=("Malgun Gothic", 12, "bold"),
            foreground="#ef4444"
        )
        title_lbl.pack(anchor="w")

        info_lbl = ttk.Label(
            header_frame,
            text="아래 버튼을 눌러 전체 오류 메시지 및 FFmpeg 실행 명령어를 클립보드에 복사할 수 있습니다.",
            font=("Malgun Gothic", 9),
            foreground="#475569"
        )
        info_lbl.pack(anchor="w", pady=(4, 0))

        # 리포트 텍스트 생성
        report_lines = [
            "================================================================================",
            f"❌ FFmpeg 오류 상세 리포트 ({self.build_version})",
            f"⏰ 발생 시각: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"📌 오류 항목: {title}",
            "================================================================================",
            ""
        ]

        if checked_items:
            report_lines.append(f"📑 [작업 대상 파일 목록 (총 {len(checked_items)}개)]:")
            for i, it in enumerate(checked_items, 1):
                res_str = f"{it.get('orig_width', 0)}x{it.get('orig_height', 0)}"
                vcodec = it.get('orig_codec', 'unknown')
                acodec = it.get('audio_codec', 'none')
                is_photo = " (정지 사진 / MJPEG)" if it.get('is_static_photo') else ""
                report_lines.append(f"  {i}. {it.get('name', 'N/A')} [{res_str}, v:{vcodec}, a:{acodec}]{is_photo}")
                report_lines.append(f"     경로: {it.get('path', '')}")
            report_lines.append("")

        if ffmpeg_cmd:
            report_lines.append("💻 [실행된 FFmpeg 명령어]:")
            report_lines.append(ffmpeg_cmd)
            report_lines.append("")

        report_lines.append("🚨 [FFmpeg 상세 에러 로그 (Stderr)]:")
        report_lines.append("-" * 80)
        report_lines.append(error_message if error_message else "프로세스가 취소되었거나 상세 에러 출력이 없습니다.")
        report_lines.append("-" * 80)

        full_report_text = "\n".join(report_lines)

        # 텍스트 에디터 영역
        txt_frame = ttk.Frame(err_dialog, padding=(12, 0, 12, 6))
        txt_frame.pack(fill="both", expand=True)

        txt = tk.Text(txt_frame, wrap="word", font=("Consolas", 9), bg="#1e1e1e", fg="#f8fafc", insertbackground="white")
        scrollbar = ttk.Scrollbar(txt_frame, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)

        txt.insert("1.0", full_report_text)
        txt.config(state="disabled")

        # 하단 버튼 프레임
        btn_frame = ttk.Frame(err_dialog, padding=12)
        btn_frame.pack(fill="x")

        status_lbl = ttk.Label(btn_frame, text="", font=("Malgun Gothic", 9, "bold"), foreground="#10b981")
        status_lbl.pack(side="top", anchor="w", pady=(0, 6))

        def copy_to_clipboard():
            err_dialog.clipboard_clear()
            err_dialog.clipboard_append(full_report_text)
            err_dialog.update()
            status_lbl.config(text="✅ 클립보드에 전체 오류 메시지가 복사되었습니다! 대화창에 Ctrl+V 로 붙여넣으세요.")

        def save_to_file():
            default_fname = f"ffmpeg_error_{time.strftime('%Y%m%d_%H%M%S')}.txt"
            filepath = filedialog.asksaveasfilename(
                parent=err_dialog,
                title="오류 로그 파일로 저장",
                initialfile=default_fname,
                defaultextension=".txt",
                filetypes=[("텍스트 파일", "*.txt"), ("모든 파일", "*.*")]
            )
            if filepath:
                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(full_report_text)
                    messagebox.showinfo("저장 완료", f"오류 로그가 성공적으로 저장되었습니다:\n{filepath}", parent=err_dialog)
                except Exception as ex:
                    messagebox.showerror("저장 오류", f"파일 저장 중 오류가 발생했습니다:\n{ex}", parent=err_dialog)

        btn_copy = ttk.Button(btn_frame, text="📋 전체 오류 내용 복사 (클립보드)", command=copy_to_clipboard)
        btn_copy.pack(side="left", padx=(0, 6))

        btn_save = ttk.Button(btn_frame, text="💾 오류 로그 파일 저장 (.txt)", command=save_to_file)
        btn_save.pack(side="left", padx=(0, 6))

        btn_close = ttk.Button(btn_frame, text="닫기", command=err_dialog.destroy)
        btn_close.pack(side="right")

    @staticmethod
    def _categorize_ffmpeg_error(stderr_str, rc, item):
        """[v4.65a] FFmpeg 오류 메시지를 분석하여 사용자 친화적 오류 분류 문자열 반환"""
        low = stderr_str.lower()
        if "could not find tag for codec" in low or "not currently supported in container" in low:
            # [v4.65a] 컨테이너-코덱 불일치 상세 안내
            orig_ext = Path(item.get('path', '')).suffix.lower() if item else ''
            if orig_ext in ('.3gp', '.3g2'):
                return "3GP 컨테이너 코덱 미지원 (3GP는 H.264 Baseline만 지원 → v4.65a에서 자동 MP4 전환 처리됨)"
            return "컨테이너-코덱 미지원 (출력 포맷이 선택한 코덱을 지원하지 않음)"
        elif "3gp" in low:
            return "3GP 관련 인코딩 오류 (구형 컨테이너 호환성 문제)"
        elif any(k in low for k in ["svt", "nvenc", "qsv", "amf", "cuda", "encoder not found", "invalid device"]):
            return "GPU/하드웨어 가속 인코더 호환성 오류 (CPU 전용 권장)"
        elif any(k in low for k in ["permission denied", "access is denied", "no space left"]):
            return "파일 저장/권한/디스크 용량 오류"
        elif "invalid argument" in low:
            return "FFmpeg 필터/인코딩 인자 오류 (Invalid Argument)"
        elif any(k in low for k in ["moov atom not found", "invalid data", "end of file"]):
            return "손상된 원본 파일 (moov atom 누락 또는 파일 손상)"
        else:
            return f"FFmpeg 일반 인코딩 오류 (에러 코드: {rc})"

    def show_batch_error_summary_dialog(self, elapsed_sec=0):
        """[v4.631e] 배치 작업 종료 후 발생한 모든 오류를 통합 집계하여 보여주는 단일 모달 창"""
        batch_errs = getattr(self, 'batch_errors', [])
        if not batch_errs:
            return

        err_dialog = tk.Toplevel(self.root)
        err_dialog.title("⚠️ 배치 작업 완료 - 인코딩 오류 집계 리포트")
        err_dialog.geometry("840x640")
        err_dialog.minsize(700, 500)
        err_dialog.transient(self.root)
        err_dialog.grab_set()

        # 헤더 프레임
        header_frame = ttk.Frame(err_dialog, padding=12)
        header_frame.pack(fill="x")

        total_file_count = len(self.file_list)
        err_count = len(batch_errs)
        success_count = max(0, total_file_count - err_count)

        title_lbl = ttk.Label(
            header_frame,
            text=f"⚠️ 작업 완료: 총 {total_file_count}개 중 {success_count}개 성공, {err_count}개 오류 발생",
            font=("Malgun Gothic", 12, "bold"),
            foreground="#d97706"
        )
        title_lbl.pack(anchor="w")

        # 범주별 통계 계산
        cat_counts = {}
        for err in batch_errs:
            cat = err.get('category', '기타 오류')
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        stats_text_lines = ["📊 [오류 종류별 통계 및 해결 설명]"]
        for cat, cnt in cat_counts.items():
            stats_text_lines.append(f"  • {cat}: {cnt}건")
            if "3GP" in cat:
                stats_text_lines.append("    └ 💡 3GP 컨테이너는 차세대 코덱(AV1/HEVC)을 지원하지 않습니다. (v4.631e에서 자동 MP4 전환 처리됨)")
            elif "GPU" in cat:
                stats_text_lines.append("    └ 💡 그래픽 카드(NVENC/QSV/AMF) 호환 오류입니다. '가속 장치'를 [CPU 전용]으로 변경하고 시도하세요.")
            elif "권한" in cat:
                stats_text_lines.append("    └ 💡 저장 폴더의 쓰기 권한 및 대상 파일 잠금 상태를 확인해 주세요.")

        stats_summary_str = "\n".join(stats_text_lines)
        lbl_stats_detail = ttk.Label(header_frame, text=stats_summary_str, justify="left", font=("Malgun Gothic", 9))
        lbl_stats_detail.pack(anchor="w", pady=(6, 0))

        # 상세 리포트 텍스트 생성
        report_lines = [
            "==================================================",
            f"📋 스마트 동영상 압축기 배치 작업 오류 집계 리포트 ({self.build_version})",
            f"⏰ 작업 완료 시각: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"⏱️ 총 소요 시간: {elapsed_sec}초",
            f"📊 처리 현황: 전체 {total_file_count}개 중 {success_count}개 성공, {err_count}개 오류",
            "==================================================",
            "",
            stats_summary_str,
            "",
            "--------------------------------------------------",
            f"📑 [오류 상세 로그 목록 (총 {err_count}건)]",
            "--------------------------------------------------"
        ]

        for i, err in enumerate(batch_errs, 1):
            report_lines.append(f"\n[{i}/{err_count}] 파일명: {err['name']}")
            report_lines.append(f"  - 원본 경로: {err['path']}")
            report_lines.append(f"  - 오류 분류: {err['category']}")
            report_lines.append(f"  - 에러 코드: {err['returncode']}")
            report_lines.append("  - 상세 로그:")
            stderr_indented = "\n".join("    " + line for line in err['stderr'].splitlines())
            report_lines.append(stderr_indented)
            report_lines.append("-" * 50)

        full_report_text = "\n".join(report_lines)

        # 텍스트 스크롤 영역
        txt_frame = ttk.Frame(err_dialog, padding=(12, 0, 12, 6))
        txt_frame.pack(fill="both", expand=True)

        txt = tk.Text(txt_frame, wrap="word", font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4", insertbackground="white")
        scrollbar = ttk.Scrollbar(txt_frame, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)

        txt.insert("1.0", full_report_text)
        txt.config(state="disabled")

        # 하단 버튼 프레임
        btn_frame = ttk.Frame(err_dialog, padding=12)
        btn_frame.pack(fill="x")

        def copy_to_clipboard():
            err_dialog.clipboard_clear()
            err_dialog.clipboard_append(full_report_text)
            err_dialog.update()
            messagebox.showinfo("복사 완료", "전체 오류 집계 리포트가 클립보드에 복사되었습니다.\nCtrl+V 로 대화창에 붙여넣을 수 있습니다.", parent=err_dialog)

        def save_to_file():
            default_fname = f"compression_errors_{time.strftime('%Y%m%d_%H%M%S')}.txt"
            filepath = filedialog.asksaveasfilename(
                parent=err_dialog,
                title="오류 리포트 파일로 저장",
                initialfile=default_fname,
                defaultextension=".txt",
                filetypes=[("텍스트 파일", "*.txt"), ("모든 파일", "*.*")]
            )
            if filepath:
                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(full_report_text)
                    messagebox.showinfo("저장 완료", f"오류 리포트가 성공적으로 저장되었습니다:\n{filepath}", parent=err_dialog)
                except Exception as ex:
                    messagebox.showerror("저장 오류", f"파일 저장 중 오류가 발생했습니다:\n{ex}", parent=err_dialog)

        btn_copy = ttk.Button(btn_frame, text="📋 전체 오류 내용 복사 (클립보드)", command=copy_to_clipboard)
        btn_copy.pack(side="left", padx=(0, 6))

        btn_save = ttk.Button(btn_frame, text="💾 오류 리포트 텍스트 파일 저장 (.txt)", command=save_to_file)
        btn_save.pack(side="left", padx=(0, 6))

        btn_close = ttk.Button(btn_frame, text="닫기", command=err_dialog.destroy)
        btn_close.pack(side="right")

    def apply_saved_config_profile(self):
        """[v4.60] 저장된 사용자 기본 인코딩 프로필 및 옵션 복원"""
        prof = self.nas_manager.data.get("encoding_profile", {})
        if not prof:
            return

        try:
            if hasattr(self, 'combo_hw') and prof.get('hw'):
                self.combo_hw.set(prof['hw'])
            if hasattr(self, 'combo_codec') and prof.get('codec'):
                self.combo_codec.set(prof['codec'])
            if hasattr(self, 'combo_format') and prof.get('format'):
                self.combo_format.set(prof['format'])
            if hasattr(self, 'combo_res') and prof.get('res'):
                self.combo_res.set(prof['res'])
            if hasattr(self, 'combo_fps') and prof.get('fps'):
                self.combo_fps.set(prof['fps'])
            if hasattr(self, 'combo_audio') and prof.get('audio'):
                self.combo_audio.set(prof['audio'])
            if hasattr(self, 'crf_var') and prof.get('crf') is not None:
                self.crf_var.set(prof['crf'])
            if hasattr(self, 'merge_mode') and prof.get('merge_mode') is not None:
                self.merge_mode.set(prof['merge_mode'])
            if hasattr(self, 'combo_merge_fit') and prof.get('merge_fit'):
                self.combo_merge_fit.set(prof['merge_fit'])
            self.update_merge_fit_state()
        except Exception:
            pass

    def save_current_config_profile(self):
        """[v4.60] 현재 인코딩 방식 설정 및 UI 옵션을 영구 보관"""
        try:
            prof = {
                "hw": self.combo_hw.get() if hasattr(self, 'combo_hw') else "",
                "codec": self.combo_codec.get() if hasattr(self, 'combo_codec') else "",
                "format": self.combo_format.get() if hasattr(self, 'combo_format') else "",
                "res": self.combo_res.get() if hasattr(self, 'combo_res') else "",
                "fps": self.combo_fps.get() if hasattr(self, 'combo_fps') else "",
                "audio": self.combo_audio.get() if hasattr(self, 'combo_audio') else "",
                "crf": self.crf_var.get() if hasattr(self, 'crf_var') else 28,
                "merge_mode": self.merge_mode.get() if hasattr(self, 'merge_mode') else False,
                "merge_fit": self.combo_merge_fit.get() if hasattr(self, 'combo_merge_fit') else ""
            }
            self.nas_manager.data["encoding_profile"] = prof
            self.nas_manager.save_config()
        except Exception:
            pass

    def on_close(self):
        """종료 시 진행 중 프로세스 정리 및 설정 자동 영구 보관"""
        self.save_current_config_profile()
        self.is_running = False
        self.precise_quality_cancel = True
        try:
            if self.current_process:
                self.current_process.terminate()
            if self.preview_process:
                self.preview_process.terminate()
            if self.precise_quality_process:
                self.precise_quality_process.terminate()
            if self.preview_popup_state:
                self._pv_stop_decoder(self.preview_popup_state)
        except Exception:
            pass
        if self.preview_temp_dir and os.path.isdir(self.preview_temp_dir):
            shutil.rmtree(self.preview_temp_dir, ignore_errors=True)
        self.root.destroy()


if __name__ == "__main__":
    if DND_SUPPORTED:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    app = SmartVideoCompressorApp(root)
    root.mainloop()
