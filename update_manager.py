"""
Модуль для проверки и управления обновлениями проекта
"""

import json
import os
import requests
from datetime import datetime
from typing import Dict, Optional
import subprocess

GITHUB_REPO = "yuliitezarygml/renatal"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}"
VERSION_FILE = "version.json"


class UpdateManager:
    """Менеджер обновлений приложения"""
    
    def __init__(self, version_file: str = VERSION_FILE):
        self.version_file = version_file
        self.version_data = self._load_version_data()
    
    def _load_version_data(self) -> Dict:
        """Загружает данные о версии из файла"""
        if not os.path.exists(self.version_file):
            return {
                "current_version": "1.0.0",
                "last_check": None,
                "update_available": False,
                "github_version": None,
                "changelog": ""
            }
        
        try:
            with open(self.version_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Ошибка при загрузке версии: {e}")
            return {}
    
    def _save_version_data(self):
        """Сохраняет данные о версии в файл"""
        try:
            with open(self.version_file, 'w', encoding='utf-8') as f:
                json.dump(self.version_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка при сохранении версии: {e}")
    
    def get_github_readme(self) -> Optional[str]:
        """Получает README с GitHub для получения информации об обновлении"""
        try:
            url = f"{GITHUB_API_URL}/readme"
            headers = {"Accept": "application/vnd.github.v3.raw"}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return response.text
            return None
        except Exception as e:
            print(f"Ошибка при получении README: {e}")
            return None
    
    def get_latest_release_info(self) -> Optional[Dict]:
        """Получает информацию о последнем релизе с GitHub"""
        try:
            url = f"{GITHUB_API_URL}/releases/latest"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Ошибка при получении информации о релизе: {e}")
            return None
    
    def get_latest_commit_info(self) -> Optional[Dict]:
        """Получает информацию о последнем коммите"""
        try:
            url = f"{GITHUB_API_URL}/commits/main"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Ошибка при получении информации о коммите: {e}")
            return None
    
    def parse_version_from_commit(self, commit_message: str) -> Optional[str]:
        """Парсит версию из сообщения коммита или README"""
        # Ищет версию в формате v1.2.3 или 1.2.3
        import re
        match = re.search(r'v?(\d+\.\d+\.\d+)', commit_message)
        if match:
            return match.group(1)
        return None
    
    def check_for_updates(self) -> Dict:
        """Проверяет наличие обновлений"""
        result = {
            "update_available": False,
            "current_version": self.version_data.get("current_version", "1.0.0"),
            "github_version": None,
            "changelog": "",
            "last_check": datetime.now().isoformat()
        }
        
        # Пытаемся получить информацию о релизе
        release_info = self.get_latest_release_info()
        
        if release_info and "tag_name" in release_info:
            github_version = release_info["tag_name"].lstrip('v')
            result["github_version"] = github_version
            result["changelog"] = release_info.get("body", "")
            
            # Сравниваем версии
            if self._compare_versions(result["current_version"], github_version) < 0:
                result["update_available"] = True
        else:
            # Если нет релизов, проверяем README
            readme = self.get_github_readme()
            if readme:
                version = self.parse_version_from_commit(readme)
                if version:
                    result["github_version"] = version
                    # Ищем информацию об обновлении в README
                    lines = readme.split('\n')
                    for i, line in enumerate(lines):
                        if 'версия' in line.lower() or 'update' in line.lower():
                            result["changelog"] = '\n'.join(lines[i:i+10])
                            break
                    
                    if self._compare_versions(result["current_version"], version) < 0:
                        result["update_available"] = True
        
        # Обновляем данные о версии
        self.version_data.update(result)
        self._save_version_data()
        
        return result
    
    def _compare_versions(self, v1: str, v2: str) -> int:
        """
        Сравнивает две версии
        Возвращает: -1 если v1 < v2, 0 если v1 == v2, 1 если v1 > v2
        """
        try:
            v1_parts = [int(x) for x in v1.split('.')]
            v2_parts = [int(x) for x in v2.split('.')]
            
            # Добавляем нули для выравнивания
            while len(v1_parts) < len(v2_parts):
                v1_parts.append(0)
            while len(v2_parts) < len(v1_parts):
                v2_parts.append(0)
            
            if v1_parts < v2_parts:
                return -1
            elif v1_parts > v2_parts:
                return 1
            else:
                return 0
        except Exception:
            return 0
    
    def get_update_notification(self) -> Optional[Dict]:
        """
        Получает информацию об обновлении для вывода в админ-панели
        """
        if self.version_data.get("update_available"):
            return {
                "has_update": True,
                "current": self.version_data.get("current_version"),
                "available": self.version_data.get("github_version"),
                "changelog": self.version_data.get("changelog", ""),
                "last_check": self.version_data.get("last_check")
            }
        return {"has_update": False}
    
    def update_local_version(self, new_version: str):
        """Обновляет локальную версию"""
        self.version_data["current_version"] = new_version
        self.version_data["update_available"] = False
        self._save_version_data()
    
    def pull_from_github(self) -> bool:
        """Загружает обновления с GitHub (git pull)"""
        try:
            result = subprocess.run(
                ["git", "pull", "origin", "main"],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Ошибка при загрузке обновлений: {e}")
            return False
    
    def get_current_version(self) -> str:
        """Получает текущую версию"""
        return self.version_data.get("current_version", "1.0.0")


# Глобальный экземпляр менеджера обновлений
update_manager = None


def init_update_manager(version_file: str = VERSION_FILE) -> UpdateManager:
    """Инициализирует менеджер обновлений"""
    global update_manager
    update_manager = UpdateManager(version_file)
    return update_manager


def get_update_manager() -> UpdateManager:
    """Получает текущий экземпляр менеджера обновлений"""
    global update_manager
    if update_manager is None:
        update_manager = UpdateManager()
    return update_manager
