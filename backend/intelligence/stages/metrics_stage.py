from typing import Dict, Any
from backend.intelligence.repository_model import RepositoryModel

class MetricsStage:
    def run(self, model: RepositoryModel) -> None:
        total_files = len(model.entities.files)
        python_files = sum(1 for f in model.entities.files.values() if f.is_python)
        total_directories = len(model.entities.directories)
        total_classes = len(model.entities.classes)
        total_functions = len(model.entities.functions)
        total_methods = len(model.entities.methods)
        total_imports = len(model.entities.imports)
        
        # approximate lines of code by just summing all file sizes or lines. We don't have exact loc yet unless we count them.
        # for MVP, we can leave lines_of_code as 0 or compute it if we want.
        lines_of_code = 0
        
        largest_file = None
        max_size = -1
        for f in model.entities.files.values():
            if f.size > max_size:
                max_size = f.size
                largest_file = f.id

        model.analyses.metrics = {
            "total_files": total_files,
            "python_files": python_files,
            "total_directories": total_directories,
            "total_classes": total_classes,
            "total_functions": total_functions,
            "total_methods": total_methods,
            "total_imports": total_imports,
            "lines_of_code": lines_of_code,
            "largest_file": largest_file,
            "largest_module": None # To be implemented
        }
        
        model.analysis_status.metrics = True
