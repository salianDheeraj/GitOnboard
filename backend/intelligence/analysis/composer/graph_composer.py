from ...rim.repository import RepositoryModel
from .views.execution import ExecutionView
from .views.architecture import ArchitectureView

class GraphComposer:
    def __init__(self, model: RepositoryModel):
        self.model = model
        
    def get_execution_view(self) -> ExecutionView:
        return ExecutionView(self.model)
        
    def get_architecture_view(self) -> ArchitectureView:
        return ArchitectureView(self.model)
