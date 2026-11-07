"""LINE 聊天視窗位置輔助工具。"""

import ctypes
import datetime
import os
import re
import sys
import tkinter as tk
from ctypes import wintypes
from tkinter import ttk


def has_student_date(title: str) -> bool:
    """只辨識名稱中含有效民國日期的個別聊天視窗。"""
    for match in re.finditer(r"(?<!\d)(\d{3})(\d{2})(\d{2})(?!\d)", title):
        try:
            datetime.date(int(match[1]) + 1911, int(match[2]), int(match[3]))
            return True
        except ValueError:
            pass
    return False


def centered_position(work: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int]:
    left, top, right, bottom = work
    return (left + max(0, (right - left - width) // 2),
            top + max(0, (bottom - top - height) // 2))


def is_relevant_window(title: str, has_owner: bool, width: int, height: int) -> bool:
    """排除細小浮動元件；無標題視窗須有擁有者才視為對話框。"""
    return width >= 200 and height >= 150 and (bool(title.strip()) or has_owner)


def fitted_size(work: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int]:
    """留出視窗外框空間，避免貼齊螢幕邊緣時擷取範圍越界。"""
    return min(width, max(1, work[2] - work[0] - 32)), min(height, max(1, work[3] - work[1] - 32))


def fits_with_margin(bounds: tuple[int, int, int, int], work: tuple[int, int, int, int], margin: int = 8) -> bool:
    return (bounds[0] >= work[0] + margin and bounds[1] >= work[1] + margin and
            bounds[2] <= work[2] - margin and bounds[3] <= work[3] - margin)


class SingleInstance:
    """同一 Windows 登入工作階段只允許一個新版助手執行。"""
    def __init__(self):
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        self.kernel32.CreateMutexW.restype = wintypes.HANDLE
        self.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel32.CloseHandle.restype = wintypes.BOOL
        self.handle = self.kernel32.CreateMutexW(None, False, "Local\\LineWindowCenterAssistantV1")
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self.already_running = ctypes.get_last_error() == 183

    def close(self):
        if self.handle:
            self.kernel32.CloseHandle(self.handle)
            self.handle = None


class Windows:
    def __init__(self):
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        try:
            self.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except (AttributeError, OSError):
            pass
        self.user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        self.user32.GetWindowRect.restype = wintypes.BOOL
        self.user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        self.user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.user32.IsWindowVisible.argtypes = [wintypes.HWND]
        self.user32.IsIconic.argtypes = [wintypes.HWND]
        self.user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
        self.user32.GetWindow.restype = wintypes.HWND
        self.user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        self.user32.SetWindowPos.restype = wintypes.BOOL
        self.user32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT]
        self.user32.SystemParametersInfoW.restype = wintypes.BOOL
        self.kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel32.OpenProcess.restype = wintypes.HANDLE
        self.kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        self.kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        self.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self.callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        self.user32.EnumWindows.argtypes = [self.callback_type, wintypes.LPARAM]
        self.user32.EnumWindows.restype = wintypes.BOOL

    def is_line(self, hwnd: int) -> bool:
        pid = wintypes.DWORD()
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        handle = self.kernel32.OpenProcess(0x1000, False, pid.value)
        if not handle:
            return False
        try:
            buf = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(buf))
            if not self.kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return False
            path = os.path.normcase(os.path.normpath(buf.value))
            expected = os.path.normcase(os.path.join(os.environ.get("LOCALAPPDATA", ""), "LINE", "bin"))
            return os.path.basename(path) == "line.exe" and path.startswith(expected + os.sep)
        finally:
            self.kernel32.CloseHandle(handle)

    def work_area(self):
        rect = wintypes.RECT()
        if not self.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
            raise ctypes.WinError(ctypes.get_last_error())
        return rect.left, rect.top, rect.right, rect.bottom

    def windows(self):
        found = []
        @self.callback_type
        def visit(hwnd, _):
            if not self.user32.IsWindowVisible(hwnd) or self.user32.IsIconic(hwnd):
                return True
            length = self.user32.GetWindowTextLengthW(hwnd)
            title = ctypes.create_unicode_buffer(length + 1)
            self.user32.GetWindowTextW(hwnd, title, len(title))
            if not self.is_line(hwnd):
                return True
            rect = wintypes.RECT()
            if (self.user32.GetWindowRect(hwnd, ctypes.byref(rect)) and
                is_relevant_window(title.value, bool(self.user32.GetWindow(hwnd, 4)),
                                   rect.right - rect.left, rect.bottom - rect.top)):
                found.append((int(hwnd), (rect.left, rect.top, rect.right, rect.bottom)))
            return True
        if not self.user32.EnumWindows(visit, 0):
            raise ctypes.WinError(ctypes.get_last_error())
        return found

    def center(self, hwnd, bounds, work):
        left, top, right, bottom = bounds
        width, height = right - left, bottom - top
        if width <= 0 or height <= 0:
            return False
        width, height = fitted_size(work, width, height)
        x, y = centered_position(work, width, height)
        # Keep z-order and focus; shrink only when needed to fit the work area.
        if not self.user32.SetWindowPos(hwnd, None, x, y, width, height, 0x0004 | 0x0010):
            raise ctypes.WinError(ctypes.get_last_error())
        rect = wintypes.RECT()
        if not self.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not fits_with_margin((rect.left, rect.top, rect.right, rect.bottom), work):
            raise ValueError("LINE 視窗移動後仍太靠近螢幕邊緣，可能無法擷取")
        return True


def main():
    if sys.platform != "win32":
        raise SystemExit("此工具僅支援 Windows。")
    instance = SingleInstance()
    if instance.already_running:
        instance.close()
        print("LINE 視窗置中助手已在執行，不再重複啟動。")
        return
    try:
        run_assistant()
    finally:
        instance.close()


def run_assistant():
    windows = Windows()
    root = tk.Tk()
    root.title("LINE 視窗置中助手")
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=18)
    frame.grid()
    ttk.Label(frame, text="自動置中已啟用", font=("Microsoft JhengHei UI", 13, "bold")).grid(sticky="w")
    ttk.Label(frame, text="LINE 的聊天、Keep 筆記及對話框會移到主螢幕中央。\n不讀取聊天內容、不輸入文字，也不傳送訊息。", justify="left").grid(sticky="w", pady=(8, 8))
    status = tk.StringVar(value="正在檢查視窗…")
    ttk.Label(frame, textvariable=status).grid(sticky="w", pady=(0, 8))
    ttk.Button(frame, text="停止並關閉", command=root.destroy).grid(sticky="e")
    seen = set()
    failed = {}

    def poll():
        nonlocal seen, failed
        try:
            work = windows.work_area()
            current = windows.windows()
            live = {hwnd for hwnd, _ in current}
            failed = {hwnd: bounds for hwnd, bounds in failed.items() if hwnd in live}
            moved = 0
            failures = []
            for hwnd, bounds in current:
                left, top, right, bottom = bounds
                outside = left < work[0] or top < work[1] or right > work[2] or bottom > work[3]
                if (hwnd not in seen or outside) and failed.get(hwnd) != bounds:
                    try:
                        moved += bool(windows.center(hwnd, bounds, work))
                        failed.pop(hwnd, None)
                    except (OSError, ValueError) as exc:
                        # Remember actual post-attempt bounds to avoid moving the same window every second.
                        failed[hwnd] = dict(windows.windows()).get(hwnd, bounds)
                        failures.append(str(exc))
            seen = live
            if failures or failed:
                status.set("部分 LINE 視窗無法完整置中，請檢查擷取畫面。")
            elif moved:
                status.set(f"已移動 {moved} 個 LINE 視窗。持續監看中。")
            elif current and any((b[2]-b[0] > work[2]-work[0] or b[3]-b[1] > work[3]-work[1]) for _, b in current):
                status.set("有聊天視窗大於螢幕，請先手動縮小。")
            else:
                status.set("持續監看中；關閉此工具即可停止。")
        except (OSError, ValueError) as exc:
            status.set(f"檢查失敗：{exc}")
        root.after(1000, poll)

    root.after(100, poll)
    root.mainloop()
