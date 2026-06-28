"""
Backup Module for CryptoAssistant
Handles automatic backup of transaction data.
"""

import os
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List
import json

# Get module logger
logger = logging.getLogger(__name__)


class BackupManager:
    """
    Manages automatic backups of transaction data.
    Creates rotating backups with configurable retention policy.
    """
    
    DEFAULT_BACKUP_DIR = "backups"
    DEFAULT_RETENTION_DAYS = 30
    DEFAULT_MAX_BACKUPS = 10
    
    def __init__(
        self,
        data_file: str,
        backup_dir: Optional[str] = None,
        retention_days: int = DEFAULT_RETENTION_DAYS,
        max_backups: int = DEFAULT_MAX_BACKUPS,
        enabled: bool = True
    ):
        """
        Initialize the backup manager.
        
        Args:
            data_file (str): Path to the main data file to backup.
            backup_dir (Optional[str]): Directory to store backups. If None, uses default.
            retention_days (int): Number of days to keep backups.
            max_backups (int): Maximum number of backups to keep.
            enabled (bool): Whether backups are enabled.
        """
        self.data_file = Path(data_file)
        self.enabled = enabled
        self.retention_days = retention_days
        self.max_backups = max_backups
        
        # Set backup directory
        if backup_dir is None:
            # Use a backups directory next to the data file
            self.backup_dir = self.data_file.parent / self.DEFAULT_BACKUP_DIR
        else:
            self.backup_dir = Path(backup_dir)
        
        # Create backup directory if it doesn't exist
        if self.enabled:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Backup manager initialized: {self.backup_dir}")
            
            # Clean up old backups on initialization
            self._cleanup_old_backups()
    
    def create_backup(self, reason: str = "manual") -> Optional[Path]:
        """
        Create a backup of the data file.
        
        Args:
            reason (str): Reason for the backup (e.g., "before_import", "manual", "auto").
        
        Returns:
            Optional[Path]: Path to the created backup file, or None if backup failed.
        """
        if not self.enabled:
            logger.debug("Backup disabled, skipping...")
            return None
        
        if not self.data_file.exists():
            logger.warning(f"Data file not found: {self.data_file}, cannot create backup")
            return None
        
        try:
            # Generate backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{self.data_file.stem}_backup_{timestamp}_{reason}.{self.data_file.suffix}"
            backup_path = self.backup_dir / backup_filename
            
            # Copy the file
            shutil.copy2(self.data_file, backup_path)
            
            logger.info(f"Backup created: {backup_path} (reason: {reason})")
            
            # Clean up old backups
            self._cleanup_old_backups()
            
            return backup_path
            
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return None
    
    def _cleanup_old_backups(self) -> int:
        """
        Remove old backups based on retention policy.
        
        Returns:
            int: Number of backups removed.
        """
        if not self.backup_dir.exists():
            return 0
        
        removed_count = 0
        now = datetime.now()
        
        # Get all backup files
        backup_files = list(self.backup_dir.glob(f"{self.data_file.stem}_backup_*.{self.data_file.suffix}"))
        
        # Sort by modification time (oldest first)
        backup_files.sort(key=lambda f: f.stat().st_mtime)
        
        # Remove backups older than retention_days
        for backup_file in backup_files:
            file_age = (now - datetime.fromtimestamp(backup_file.stat().st_mtime)).days
            if file_age > self.retention_days:
                try:
                    backup_file.unlink()
                    logger.debug(f"Removed old backup: {backup_file} (age: {file_age} days)")
                    removed_count += 1
                except Exception as e:
                    logger.error(f"Failed to remove old backup {backup_file}: {e}")
        
        # If we still have too many backups, remove the oldest ones
        backup_files = list(self.backup_dir.glob(f"{self.data_file.stem}_backup_*.{self.data_file.suffix}"))
        while len(backup_files) > self.max_backups:
            oldest = min(backup_files, key=lambda f: f.stat().st_mtime)
            try:
                oldest.unlink()
                logger.debug(f"Removed excess backup: {oldest}")
                removed_count += 1
                backup_files.remove(oldest)
            except Exception as e:
                logger.error(f"Failed to remove excess backup {oldest}: {e}")
                break
        
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old backups")
        
        return removed_count
    
    def get_backup_list(self) -> List[dict]:
        """
        Get a list of all available backups.
        
        Returns:
            List[dict]: List of backup info dictionaries with keys:
                - filename: Backup filename
                - path: Full path to backup
                - size: File size in bytes
                - modified: Modification timestamp
                - age_days: Age in days
        """
        if not self.backup_dir.exists():
            return []
        
        backups = []
        now = datetime.now()
        
        backup_files = list(self.backup_dir.glob(f"{self.data_file.stem}_backup_*.{self.data_file.suffix}"))
        backup_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        
        for backup_file in backup_files:
            stat = backup_file.stat()
            age = (now - datetime.fromtimestamp(stat.st_mtime)).days
            backups.append({
                'filename': backup_file.name,
                'path': str(backup_file),
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                'age_days': age
            })
        
        return backups
    
    def restore_backup(self, backup_path: str) -> bool:
        """
        Restore a backup file to the original location.
        
        Args:
            backup_path (str): Path to the backup file to restore.
        
        Returns:
            bool: True if restore was successful, False otherwise.
        """
        backup_path = Path(backup_path)
        
        if not backup_path.exists():
            logger.error(f"Backup file not found: {backup_path}")
            return False
        
        try:
            # Create a backup of the current file before restoring
            self.create_backup(reason="before_restore")
            
            # Copy backup to original location
            shutil.copy2(backup_path, self.data_file)
            
            logger.info(f"Restored backup: {backup_path} -> {self.data_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            return False
    
    def get_latest_backup(self) -> Optional[Path]:
        """
        Get the path to the latest backup.
        
        Returns:
            Optional[Path]: Path to the latest backup, or None if no backups exist.
        """
        if not self.backup_dir.exists():
            return None
        
        backup_files = list(self.backup_dir.glob(f"{self.data_file.stem}_backup_*.{self.data_file.suffix}"))
        
        if not backup_files:
            return None
        
        # Return the most recently modified backup
        return max(backup_files, key=lambda f: f.stat().st_mtime)


def create_backup_manager(
    data_file: str,
    backup_dir: Optional[str] = None,
    retention_days: int = 30,
    max_backups: int = 10,
    enabled: bool = True
) -> BackupManager:
    """
    Factory function to create a BackupManager instance.
    
    Args:
        data_file (str): Path to the main data file.
        backup_dir (Optional[str]): Directory to store backups.
        retention_days (int): Number of days to keep backups.
        max_backups (int): Maximum number of backups to keep.
        enabled (bool): Whether backups are enabled.
    
    Returns:
        BackupManager: Configured backup manager instance.
    """
    return BackupManager(
        data_file=data_file,
        backup_dir=backup_dir,
        retention_days=retention_days,
        max_backups=max_backups,
        enabled=enabled
    )
