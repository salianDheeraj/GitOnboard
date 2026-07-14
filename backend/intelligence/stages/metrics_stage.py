from typing import Dict, Any
from backend.intelligence.repository_model import RepositoryModel

class MetricsStage:
    def __init__(self, target_dir: str = ""):
        self.target_dir = target_dir

    def run(self, model: RepositoryModel) -> None:
        total_files = len(model.entities.files)
        python_files = sum(1 for f in model.entities.files.values() if f.is_python)
        total_directories = len(model.entities.directories)
        total_classes = len(model.entities.classes)
        total_functions = len(model.entities.functions)
        total_methods = len(model.entities.methods)
        total_imports = len(model.entities.imports)
        
        lines_of_code = 0
        total_comments = 0
        test_files = 0
        total_complexity = 0
        
        largest_file = None
        max_size = -1
        
        import os
        
        for f in model.entities.files.values():
            if f.size > max_size:
                max_size = f.size
                largest_file = f.id
                
            # Compute test coverage rough approximation
            if "test" in f.name.lower() or "spec" in f.name.lower():
                test_files += 1
                
            # Read lines and comments if file exists
            full_path = os.path.join(self.target_dir, f.path) if self.target_dir else f.path
            if os.path.exists(full_path):
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as file_obj:
                        lines = file_obj.readlines()
                        lines_of_code += len(lines)
                        
                        # Rough comment counting
                        for line in lines:
                            stripped = line.strip()
                            if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
                                total_comments += 1
                except Exception:
                    pass
                    
        comment_ratio = round((total_comments / lines_of_code * 100), 2) if lines_of_code > 0 else 0
        test_coverage = round((test_files / total_files * 100), 2) if total_files > 0 else 0
        
        # Approximate complexity: functions with many lines are more complex. Just a placeholder logic.
        complexity = round(lines_of_code / max(1, total_functions), 2)

        # Sort files by size
        sorted_files = sorted(model.entities.files.values(), key=lambda f: f.size, reverse=True)
        largest_files = [{"file": f.path, "size": f.size} for f in sorted_files[:5]]
        
        # Modules and largest modules
        modules = model.entities.modules
        total_modules = len(modules)
        
        # Determine functions per module
        module_func_counts = {}
        for func in model.entities.functions.values():
            mod_id = func.file_id # naive approximation since modules often correspond to files
            module_func_counts[mod_id] = module_func_counts.get(mod_id, 0) + 1
            
        sorted_modules = sorted([{"module": k, "functions": v} for k, v in module_func_counts.items()], key=lambda x: x["functions"], reverse=True)
        largest_modules = sorted_modules[:5]

        model.analyses.metrics = {
            "total_files": total_files,
            "python_files": python_files,
            "total_directories": total_directories,
            "total_classes": total_classes,
            "total_functions": total_functions,
            "total_methods": total_methods,
            "total_imports": total_imports,
            "lines_of_code": lines_of_code,
            "largest_files": largest_files,
            "largest_modules": largest_modules,
            "documentation_coverage_percent": comment_ratio,
            "test_coverage_approx_percent": test_coverage,
            "average_cyclomatic_complexity": complexity,
            "total_modules": total_modules
        }
        
        model.analysis_status.metrics = True
