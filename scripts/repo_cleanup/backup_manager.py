#!/usr/bin/env python3
"""
Backup Manager - Creates safety backups before cleanup operations
"""
import os
import shutil
import tarfile
from pathlib import Path
from datetime import datetime
import json
import hashlib


class BackupManager:
    """Manages repository backups"""

    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root)
        self.backup_dir = self.repo_root / 'backups'
        self.backup_dir.mkdir(exist_ok=True)

        # Directories to exclude from backup
        self.exclude_dirs = {
            '.git', '__pycache__', '.pytest_cache',
            'node_modules', '.venv', 'venv',
            'htmlcov', 'backups', 'pids', 'logs'
        }

        # File patterns to exclude
        self.exclude_patterns = {
            '*.pyc', '*.log', '*.tmp',
            '.DS_Store', '*.swp', '*.swo'
        }

    def should_exclude(self, path: Path) -> bool:
        """Check if path should be excluded from backup"""
        # Check directory names
        parts = path.parts
        if any(part in self.exclude_dirs for part in parts):
            return True

        # Check file patterns
        for pattern in self.exclude_patterns:
            if path.match(pattern):
                return True

        return False

    def calculate_checksum(self, file_path: Path) -> str:
        """Calculate MD5 checksum of a file"""
        md5 = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                md5.update(chunk)
        return md5.hexdigest()

    def create_snapshot(self, description: str = "Pre-cleanup backup") -> dict:
        """Create a snapshot of current repository state"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        snapshot_name = f"snapshot_{timestamp}"
        snapshot_dir = self.backup_dir / snapshot_name
        snapshot_dir.mkdir(exist_ok=True)

        print(f"📸 Creating snapshot: {snapshot_name}")
        print(f"Description: {description}")

        # Create manifest
        manifest = {
            'timestamp': timestamp,
            'description': description,
            'files': {}
        }

        # Copy files
        copied_count = 0
        total_size = 0

        for root, dirs, files in os.walk(self.repo_root):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]

            root_path = Path(root)

            for file in files:
                file_path = root_path / file

                if self.should_exclude(file_path):
                    continue

                # Calculate relative path
                try:
                    rel_path = file_path.relative_to(self.repo_root)
                except ValueError:
                    continue

                # Create destination
                dest_path = snapshot_dir / rel_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)

                # Copy file
                try:
                    shutil.copy2(file_path, dest_path)

                    # Add to manifest
                    checksum = self.calculate_checksum(file_path)
                    file_size = file_path.stat().st_size

                    manifest['files'][str(rel_path)] = {
                        'checksum': checksum,
                        'size': file_size,
                        'modified': datetime.fromtimestamp(
                            file_path.stat().st_mtime
                        ).isoformat()
                    }

                    copied_count += 1
                    total_size += file_size

                    if copied_count % 100 == 0:
                        print(f"  Copied {copied_count} files...")

                except Exception as e:
                    print(f"  ⚠️  Warning: Could not backup {rel_path}: {e}")

        # Save manifest
        manifest['total_files'] = copied_count
        manifest['total_size'] = total_size

        manifest_path = snapshot_dir / 'manifest.json'
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)

        print(f"✅ Snapshot created successfully!")
        print(f"   Files: {copied_count}")
        print(f"   Size: {total_size / (1024 * 1024):.2f} MB")
        print(f"   Location: {snapshot_dir}")

        return {
            'name': snapshot_name,
            'path': str(snapshot_dir),
            'files': copied_count,
            'size': total_size,
            'timestamp': timestamp
        }

    def create_archive(self, snapshot_name: str = None) -> str:
        """Create compressed archive of snapshot"""
        if snapshot_name is None:
            # Find most recent snapshot
            snapshots = sorted([d for d in self.backup_dir.iterdir() if d.is_dir()])
            if not snapshots:
                raise ValueError("No snapshots found to archive")
            snapshot_dir = snapshots[-1]
        else:
            snapshot_dir = self.backup_dir / snapshot_name

        if not snapshot_dir.exists():
            raise ValueError(f"Snapshot not found: {snapshot_name}")

        # Create archive
        archive_path = self.backup_dir / f"{snapshot_dir.name}.tar.gz"

        print(f"📦 Creating archive: {archive_path.name}")

        with tarfile.open(archive_path, 'w:gz') as tar:
            tar.add(snapshot_dir, arcname=snapshot_dir.name)

        archive_size = archive_path.stat().st_size
        print(f"✅ Archive created: {archive_size / (1024 * 1024):.2f} MB")

        return str(archive_path)

    def list_backups(self):
        """List all available backups"""
        print("\n📋 Available Backups:")
        print("="*60)

        snapshots = sorted([d for d in self.backup_dir.iterdir() if d.is_dir()])
        archives = sorted([f for f in self.backup_dir.iterdir() if f.suffix == '.gz'])

        if snapshots:
            print("\nSnapshots:")
            for snapshot in snapshots:
                manifest_path = snapshot / 'manifest.json'
                if manifest_path.exists():
                    with open(manifest_path) as f:
                        manifest = json.load(f)
                    print(f"  - {snapshot.name}")
                    print(f"    Description: {manifest.get('description', 'N/A')}")
                    print(f"    Files: {manifest.get('total_files', 'N/A')}")
                    print(f"    Size: {manifest.get('total_size', 0) / (1024*1024):.2f} MB")

        if archives:
            print("\nArchives:")
            for archive in archives:
                size = archive.stat().st_size / (1024 * 1024)
                print(f"  - {archive.name} ({size:.2f} MB)")

        if not snapshots and not archives:
            print("  No backups found")

    def restore_snapshot(self, snapshot_name: str, target_dir: str = None):
        """Restore a snapshot"""
        snapshot_dir = self.backup_dir / snapshot_name

        if not snapshot_dir.exists():
            raise ValueError(f"Snapshot not found: {snapshot_name}")

        if target_dir is None:
            target_dir = self.repo_root
        else:
            target_dir = Path(target_dir)

        print(f"♻️  Restoring snapshot: {snapshot_name}")
        print(f"Target: {target_dir}")

        # Load manifest
        manifest_path = snapshot_dir / 'manifest.json'
        if not manifest_path.exists():
            raise ValueError("Snapshot manifest not found")

        with open(manifest_path) as f:
            manifest = json.load(f)

        # Confirm restore
        print(f"\n⚠️  This will restore {manifest['total_files']} files")
        response = input("Continue? (yes/no): ")

        if response.lower() != 'yes':
            print("Restore cancelled")
            return

        # Restore files
        restored_count = 0

        for rel_path_str in manifest['files']:
            source = snapshot_dir / rel_path_str
            dest = target_dir / rel_path_str

            dest.parent.mkdir(parents=True, exist_ok=True)

            try:
                shutil.copy2(source, dest)
                restored_count += 1

                if restored_count % 100 == 0:
                    print(f"  Restored {restored_count} files...")

            except Exception as e:
                print(f"  ⚠️  Warning: Could not restore {rel_path_str}: {e}")

        print(f"✅ Restore complete! Restored {restored_count} files")

    def verify_snapshot(self, snapshot_name: str) -> bool:
        """Verify integrity of a snapshot"""
        snapshot_dir = self.backup_dir / snapshot_name

        if not snapshot_dir.exists():
            raise ValueError(f"Snapshot not found: {snapshot_name}")

        print(f"🔍 Verifying snapshot: {snapshot_name}")

        manifest_path = snapshot_dir / 'manifest.json'
        if not manifest_path.exists():
            print("❌ Manifest not found")
            return False

        with open(manifest_path) as f:
            manifest = json.load(f)

        verified_count = 0
        failed_count = 0

        for rel_path_str, file_info in manifest['files'].items():
            file_path = snapshot_dir / rel_path_str

            if not file_path.exists():
                print(f"  ❌ Missing: {rel_path_str}")
                failed_count += 1
                continue

            # Verify checksum
            current_checksum = self.calculate_checksum(file_path)
            expected_checksum = file_info['checksum']

            if current_checksum != expected_checksum:
                print(f"  ❌ Checksum mismatch: {rel_path_str}")
                failed_count += 1
            else:
                verified_count += 1

        total = verified_count + failed_count
        print(f"\n{'✅' if failed_count == 0 else '⚠️'} Verification complete:")
        print(f"  Verified: {verified_count}/{total}")
        print(f"  Failed: {failed_count}/{total}")

        return failed_count == 0


def main():
    """Main execution"""
    import sys

    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    manager = BackupManager(repo_root)

    if len(sys.argv) < 2:
        print("🔐 Backup Manager")
        print("\nUsage:")
        print("  python backup_manager.py create [description]")
        print("  python backup_manager.py list")
        print("  python backup_manager.py archive [snapshot_name]")
        print("  python backup_manager.py verify <snapshot_name>")
        print("  python backup_manager.py restore <snapshot_name>")
        return

    command = sys.argv[1]

    if command == 'create':
        description = sys.argv[2] if len(sys.argv) > 2 else "Manual backup"
        manager.create_snapshot(description)

    elif command == 'list':
        manager.list_backups()

    elif command == 'archive':
        snapshot_name = sys.argv[2] if len(sys.argv) > 2 else None
        manager.create_archive(snapshot_name)

    elif command == 'verify':
        if len(sys.argv) < 3:
            print("❌ Error: Snapshot name required")
            return
        manager.verify_snapshot(sys.argv[2])

    elif command == 'restore':
        if len(sys.argv) < 3:
            print("❌ Error: Snapshot name required")
            return
        manager.restore_snapshot(sys.argv[2])

    else:
        print(f"❌ Unknown command: {command}")


if __name__ == '__main__':
    main()
