"""
GitHub Skill 加载器
从 GitHub 仓库下载并安装 SKILL.md 格式的 Agent Skill。

兼容 Agent Skills 规范（langchain-skills / Anthropic / Claude Code 等生态）。

使用示例：
    from src.skills.github_loader import install_skill_from_github

    # 安装单个 Skill
    install_skill_from_github(
        repo="langchain-ai/langchain-skills",
        skill_name="langgraph-fundamentals",
    )

    # 安装仓库中的所有 Skill
    install_all_skills_from_github(
        repo="langchain-ai/langchain-skills",
    )
"""
from __future__ import annotations

import json
import logging
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from src.skills.base import get_registry

logger = logging.getLogger(__name__)

# 默认 Skill 安装目录
DEFAULT_SKILLS_DIR = Path(__file__).parent.parent.parent / "skills" / "community"


def install_skill_from_github(
    repo: str,
    skill_name: str,
    branch: str = "main",
    skills_subdir: str = "skills",
    install_dir: Path | None = None,
) -> bool:
    """
    从 GitHub 仓库下载单个 SKILL.md Skill。

    Args:
        repo: GitHub 仓库（格式：owner/repo）
        skill_name: Skill 名称（即子目录名）
        branch: 分支名
        skills_subdir: 仓库中 Skill 所在的子目录
        install_dir: 安装目标目录

    Returns:
        是否安装成功
    """
    install_dir = install_dir or DEFAULT_SKILLS_DIR
    install_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 下载仓库 ZIP
        zip_url = f"https://github.com/{repo}/archive/refs/heads/{branch}.zip"
        logger.info(f"从 GitHub 下载 Skill: {repo}/{skills_subdir}/{skill_name}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "repo.zip"

            # 下载
            urllib.request.urlretrieve(zip_url, str(zip_path))

            # 解压
            with zipfile.ZipFile(str(zip_path), "r") as zf:
                zf.extractall(tmp_dir)

            # 定位 Skill 目录
            # ZIP 解压后通常是 repo-branch/ 目录
            repo_name = repo.split("/")[-1]
            extracted_dir = Path(tmp_dir) / f"{repo_name}-{branch}"

            if not extracted_dir.exists():
                # 有时目录名不同，遍历查找
                for d in Path(tmp_dir).iterdir():
                    if d.is_dir() and d.name != "__MACOSX":
                        extracted_dir = d
                        break

            skill_source = extracted_dir / skills_subdir / skill_name

            if not skill_source.exists():
                logger.error(f"Skill 不存在: {skill_source}")
                return False

            skill_md = skill_source / "SKILL.md"
            if not skill_md.exists():
                logger.error(f"SKILL.md 不存在: {skill_md}")
                return False

            # 复制到安装目录
            dest = install_dir / skill_name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(str(skill_source), str(dest))

            logger.info(f"Skill 已安装: {dest}")

            # 注册到 Registry
            registry = get_registry()
            registry.load_from_directory(install_dir)

            return True

    except Exception as e:
        logger.error(f"安装 Skill 失败 [{repo}/{skill_name}]: {e}")
        return False


def install_all_skills_from_github(
    repo: str,
    branch: str = "main",
    skills_subdir: str = "skills",
    install_dir: Path | None = None,
) -> int:
    """
    从 GitHub 仓库下载所有 SKILL.md Skill。

    Args:
        repo: GitHub 仓库（格式：owner/repo）
        branch: 分支名
        skills_subdir: 仓库中 Skill 所在的子目录
        install_dir: 安装目标目录

    Returns:
        安装成功的 Skill 数量
    """
    install_dir = install_dir or DEFAULT_SKILLS_DIR
    install_dir.mkdir(parents=True, exist_ok=True)

    try:
        zip_url = f"https://github.com/{repo}/archive/refs/heads/{branch}.zip"
        logger.info(f"从 GitHub 下载所有 Skill: {repo}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "repo.zip"
            urllib.request.urlretrieve(zip_url, str(zip_path))

            with zipfile.ZipFile(str(zip_path), "r") as zf:
                zf.extractall(tmp_dir)

            repo_name = repo.split("/")[-1]
            extracted_dir = Path(tmp_dir) / f"{repo_name}-{branch}"

            if not extracted_dir.exists():
                for d in Path(tmp_dir).iterdir():
                    if d.is_dir() and d.name != "__MACOSX":
                        extracted_dir = d
                        break

            skills_source = extracted_dir / skills_subdir
            if not skills_source.exists():
                logger.error(f"Skill 目录不存在: {skills_source}")
                return 0

            installed = 0
            for skill_dir in sorted(skills_source.iterdir()):
                if not skill_dir.is_dir():
                    continue
                if not (skill_dir / "SKILL.md").exists():
                    continue

                dest = install_dir / skill_dir.name
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(str(skill_dir), str(dest))
                installed += 1
                logger.info(f"Skill 已安装: {skill_dir.name}")

            # 批量注册
            registry = get_registry()
            registry.load_from_directory(install_dir)

            logger.info(f"共安装 {installed} 个 Skill")
            return installed

    except Exception as e:
        logger.error(f"批量安装 Skill 失败 [{repo}]: {e}")
        return 0


def list_github_skills(
    repo: str,
    branch: str = "main",
    skills_subdir: str = "skills",
) -> list[dict[str, str]]:
    """
    列出 GitHub 仓库中可用的 Skill（不下载）。

    通过 GitHub API 获取目录列表。

    Returns:
        [{"name": "skill-name", "path": "skills/skill-name"}, ...]
    """
    api_url = (
        f"https://api.github.com/repos/{repo}"
        f"/contents/{skills_subdir}?ref={branch}"
    )

    try:
        req = urllib.request.Request(
            api_url,
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        skills = []
        for item in data:
            if item["type"] == "dir":
                skills.append({
                    "name": item["name"],
                    "path": item["path"],
                    "url": item["html_url"],
                })

        return skills

    except Exception as e:
        logger.error(f"获取 Skill 列表失败 [{repo}]: {e}")
        return []
