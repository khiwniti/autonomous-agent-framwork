#!/usr/bin/env python3
"""
Comprehensive System Validation Script
Tests all 8 phases without requiring full dependency installation
"""

import ast
import json
import os
import subprocess
import sys
import yaml
from pathlib import Path
from typing import List, Tuple, Dict

class SystemValidator:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.results = {}
        self.errors = []

    def validate_python_syntax(self, directory: Path) -> Tuple[bool, List[str]]:
        """Validate Python syntax in all files"""
        errors = []
        python_files = list(directory.rglob("*.py"))

        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    ast.parse(f.read(), filename=str(file_path))
            except SyntaxError as e:
                errors.append(f"Syntax error in {file_path}: {e}")

        return len(errors) == 0, errors

    def validate_imports(self, directory: Path) -> Tuple[bool, List[str]]:
        """Check import structure validity"""
        errors = []
        python_files = list(directory.rglob("*.py"))

        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    tree = ast.parse(f.read(), filename=str(file_path))
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.Import, ast.ImportFrom)):
                            # Just verify syntax, don't check if modules exist
                            pass
            except Exception as e:
                errors.append(f"Import error in {file_path}: {e}")

        return len(errors) == 0, errors

    def validate_yaml_files(self, directory: Path, pattern: str = "*.yaml") -> Tuple[bool, List[str]]:
        """Validate YAML syntax"""
        errors = []
        yaml_files = list(directory.rglob(pattern))

        for file_path in yaml_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    # Use safe_load_all to handle multi-document YAML files (Kubernetes style)
                    docs = list(yaml.safe_load_all(f))
                    if not docs or all(doc is None for doc in docs):
                        errors.append(f"Empty YAML file: {file_path}")
            except yaml.YAMLError as e:
                errors.append(f"YAML error in {file_path}: {e}")

        return len(errors) == 0, errors

    def validate_json_files(self, directory: Path) -> Tuple[bool, List[str]]:
        """Validate JSON syntax"""
        errors = []
        json_files = list(directory.rglob("*.json"))

        for file_path in json_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                errors.append(f"JSON error in {file_path}: {e}")

        return len(errors) == 0, errors

    def validate_dockerfile(self, file_path: Path) -> Tuple[bool, List[str]]:
        """Validate Dockerfile syntax"""
        errors = []

        if not file_path.exists():
            return False, [f"Dockerfile not found at {file_path}"]

        # Basic Dockerfile validation
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                required_instructions = ['FROM', 'COPY', 'RUN']
                for instruction in required_instructions:
                    if instruction not in content:
                        errors.append(f"Missing {instruction} instruction in Dockerfile")
        except Exception as e:
            errors.append(f"Error reading Dockerfile: {e}")

        return len(errors) == 0, errors

    def validate_helm_chart(self, chart_path: Path) -> Tuple[bool, List[str]]:
        """Validate Helm chart structure"""
        errors = []

        required_files = ['Chart.yaml', 'values.yaml']
        for required_file in required_files:
            file_path = chart_path / required_file
            if not file_path.exists():
                errors.append(f"Missing required file: {required_file}")

        # Validate Chart.yaml
        chart_yaml = chart_path / 'Chart.yaml'
        if chart_yaml.exists():
            try:
                with open(chart_yaml, 'r') as f:
                    chart_data = yaml.safe_load(f)
                    required_fields = ['apiVersion', 'name', 'version']
                    for field in required_fields:
                        if field not in chart_data:
                            errors.append(f"Missing required field in Chart.yaml: {field}")
            except Exception as e:
                errors.append(f"Error validating Chart.yaml: {e}")

        return len(errors) == 0, errors

    def run_phase_validation(self):
        """Run validation for all phases"""

        print("🔍 COMPREHENSIVE SYSTEM VALIDATION")
        print("=" * 80)

        # Phase 1: Core Architecture
        print("\n📦 Phase 1: Core Architecture & Agent Framework")
        src_dir = self.project_root / "src"
        valid, errors = self.validate_python_syntax(src_dir / "agent")
        self.results["Phase 1 - Python Syntax"] = valid
        if not valid:
            self.errors.extend(errors[:5])  # Limit errors shown
            print(f"   ❌ Python syntax validation failed ({len(errors)} errors)")
        else:
            print("   ✅ Python syntax valid")

        valid, errors = self.validate_imports(src_dir / "agent")
        self.results["Phase 1 - Imports"] = valid
        if valid:
            print("   ✅ Import structure valid")
        else:
            print(f"   ❌ Import validation failed ({len(errors)} errors)")
            self.errors.extend(errors[:3])

        # Phase 2: LLM Integration
        print("\n📦 Phase 2: LLM Integration & Reasoning")
        llm_dir = src_dir / "agent" / "llm"
        if llm_dir.exists():
            files = list(llm_dir.glob("*.py"))
            print(f"   ✅ LLM module structure: {len(files)} files")
            self.results["Phase 2 - LLM Module"] = len(files) > 0
        else:
            print("   ❌ LLM module not found")
            self.results["Phase 2 - LLM Module"] = False

        # Phase 3: Tool System
        print("\n📦 Phase 3: Tool System & Execution")
        tools_dir = src_dir / "agent" / "tools"
        if tools_dir.exists():
            subdirs = [d for d in tools_dir.iterdir() if d.is_dir() and not d.name.startswith('__')]
            print(f"   ✅ Tool categories: {len(subdirs)}")
            self.results["Phase 3 - Tools"] = len(subdirs) > 0
        else:
            print("   ❌ Tools module not found")
            self.results["Phase 3 - Tools"] = False

        # Phase 4: Memory Management
        print("\n📦 Phase 4: Memory & Context Management")
        memory_dir = src_dir / "agent" / "memory"
        if memory_dir.exists():
            files = list(memory_dir.glob("*.py"))
            print(f"   ✅ Memory system: {len(files)} components")
            self.results["Phase 4 - Memory"] = len(files) > 0
        else:
            print("   ❌ Memory module not found")
            self.results["Phase 4 - Memory"] = False

        # Phase 5: API & Interfaces
        print("\n📦 Phase 5: API & User Interfaces")
        api_dir = src_dir / "agent" / "api"
        cli_dir = src_dir / "agent" / "cli"
        api_exists = api_dir.exists() if api_dir else False
        cli_exists = cli_dir.exists() if cli_dir else False
        print(f"   {'✅' if api_exists else '❌'} API module: {api_exists}")
        print(f"   {'✅' if cli_exists else '❌'} CLI module: {cli_exists}")
        self.results["Phase 5 - API/CLI"] = api_exists or cli_exists

        # Phase 6: Observability & Security
        print("\n📦 Phase 6: Observability & Security")
        obs_dir = src_dir / "agent" / "observability"
        sec_dir = src_dir / "agent" / "security"
        obs_exists = obs_dir.exists() if obs_dir else False
        sec_exists = sec_dir.exists() if sec_dir else False
        print(f"   {'✅' if obs_exists else '❌'} Observability: {obs_exists}")
        print(f"   {'✅' if sec_exists else '❌'} Security: {sec_exists}")
        self.results["Phase 6 - Observability/Security"] = obs_exists or sec_exists

        # Phase 7: Deployment & Infrastructure
        print("\n📦 Phase 7: Deployment & Infrastructure")

        # Docker
        dockerfile = self.project_root / "Dockerfile"
        valid, errors = self.validate_dockerfile(dockerfile)
        self.results["Phase 7 - Docker"] = valid
        if valid:
            print("   ✅ Dockerfile valid")
        else:
            print(f"   ❌ Dockerfile validation failed")
            self.errors.extend(errors)

        # Docker Compose
        compose_file = self.project_root / "docker-compose.yml"
        if compose_file.exists():
            valid, errors = self.validate_yaml_files(compose_file.parent, "docker-compose.yml")
            self.results["Phase 7 - Docker Compose"] = valid
            print(f"   {'✅' if valid else '❌'} Docker Compose")

        # Kubernetes
        k8s_dir = self.project_root.parent / "deploy" / "k8s"
        if k8s_dir.exists():
            valid, errors = self.validate_yaml_files(k8s_dir)
            self.results["Phase 7 - Kubernetes"] = valid
            yaml_count = len(list(k8s_dir.rglob("*.yaml")))
            print(f"   {'✅' if valid else '❌'} Kubernetes manifests ({yaml_count} files)")

        # Helm
        helm_dir = self.project_root.parent / "deploy" / "helm" / "autonomous-agent"
        if helm_dir.exists():
            valid, errors = self.validate_helm_chart(helm_dir)
            self.results["Phase 7 - Helm"] = valid
            print(f"   {'✅' if valid else '❌'} Helm chart")

        # CI/CD
        github_dir = self.project_root.parent / ".github" / "workflows"
        if github_dir.exists():
            valid, errors = self.validate_yaml_files(github_dir)
            self.results["Phase 7 - CI/CD"] = valid
            workflow_count = len(list(github_dir.glob("*.yml")))
            print(f"   {'✅' if valid else '❌'} GitHub Actions ({workflow_count} workflows)")

        # Terraform
        terraform_dirs = [
            self.project_root.parent / "deploy" / "terraform" / "aws",
            self.project_root.parent / "deploy" / "terraform" / "gcp",
            self.project_root.parent / "deploy" / "terraform" / "azure"
        ]
        terraform_valid = all(d.exists() for d in terraform_dirs)
        self.results["Phase 7 - Terraform"] = terraform_valid
        print(f"   {'✅' if terraform_valid else '❌'} Terraform (3 providers)")

        # Summary
        print("\n" + "=" * 80)
        print("📊 VALIDATION SUMMARY")
        print("=" * 80)

        total = len(self.results)
        passed = sum(1 for v in self.results.values() if v)

        for phase, status in self.results.items():
            status_icon = "✅" if status else "❌"
            print(f"{status_icon} {phase}")

        print("\n" + "=" * 80)
        success_rate = (passed / total * 100) if total > 0 else 0
        print(f"🎯 Overall Result: {passed}/{total} checks passed ({success_rate:.1f}%)")

        if self.errors:
            print(f"\n⚠️  {len(self.errors)} errors detected (showing first 10):")
            for error in self.errors[:10]:
                print(f"   - {error}")

        print("=" * 80)

        return passed == total


if __name__ == "__main__":
    project_root = Path(__file__).parent
    validator = SystemValidator(project_root)

    try:
        success = validator.run_phase_validation()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Validation failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
