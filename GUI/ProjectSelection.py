from PySide6.QtCore import Qt

from GUI.ProjectViewModel import BatchItem, SceneItem

class SelectedScene:
    def __init__(self, scene : SceneItem, selected : bool = True) -> None:
        self.number = scene.number
        self.selected = selected
        self.batches = {}

    def __getitem__(self, index):
        return self.batches[index]
    
    def __setitem__(self, index, value):
        self.batches[index] = value

class SelectedBatch:
    def __init__(self, batch : BatchItem, selected : bool = True) -> None:
        self.scene = batch.scene
        self.number = batch.number
        self.selected = selected
        self.originals = {}
        self.translated = {}

class ProjectSelection():
    def __init__(self) -> None:
        self.scenes = {}

    @property
    def scene_numbers(self) -> list[int]:
        return sorted([ key for key in self.scenes.keys() ])
    
    @property
    def selected_scenes(self) -> list[SelectedScene]:
        return [ selection.number for selection in self.scenes.values() if selection.selected]
    
    @property
    def batch_numbers(self) -> list[(int,int)]:
        batches = []
        for scene in self.scenes.values():
            batches.extend([ (scene.number, key) for key in scene.batches.keys() ])
        return sorted(batches)

    @property
    def selected_batches(self) -> list[SelectedBatch]:
        batches = []
        for scene in self.scenes.values():
            batches.extend([ batch for batch in scene.batches.values() if batch.selected])
        return batches

    @property
    def originals(self) -> list[int]:
        originals = []
        for scene, batch in self.batch_numbers:
            originals.extend(self.scenes[scene][batch].originals.values())
        return originals

    @property
    def translated(self) -> list[int]:
        translated = []
        for scene, batch in self.batch_numbers:
            translated.extend( key for key in self.scenes[scene][batch].translated.values())
        return translated

    def Any(self) -> bool:
        return self.scene_numbers or self.batch_numbers or self.originals or self.translated
    
    def AnyScenes(self) -> bool:
        return self.selected_scenes and True
    
    def OnlyScenes(self) -> bool:
        return self.selected_scenes and not self.selected_batches
    
    def AnyBatches(self) -> bool:
        return self.selected_batches and True

    def OnlyBatches(self) -> bool:
        return self.selected_batches and not self.selected_scenes

    def MultipleSelected(self) -> bool:
        return len(self.selected_scenes) > 1 or len(self.selected_batches) > 1
    
    def SelectionIsSequential(self) -> bool:
        if self.selected_scenes:
            scene_numbers = self.scene_numbers
            if scene_numbers != list(range(self.scene_numbers[0], self.scene_numbers[0] + len(self.scene_numbers))):
                return False
            
        if self.selected_batches:
            batches = self.selected_batches

            if not all(batch.scene == batches[0].scene for batch in batches):
                return False

            batch_numbers = [ batch.number for batch in batches ]
            if batch_numbers != list(range(batch_numbers[0], batch_numbers[0] + len(batches))):
                return False
        
        return True

    def GetSelectionMap(self):
        selection = {}
        for scene in self.scenes.values():
            selection[scene.number] = { 'selected' : scene.selected }

            for batch in scene.batches.values():
                selection[scene.number][batch.number] = { 
                    'selected' : True,
                    'originals' : batch.originals.keys(),
                    'translated' : batch.translated.keys() 
                    }

        return selection

    def AppendItem(self, model, index, selected : bool = True):
        """
        Accumulated selected batches, scenes and lines
        """
        item = model.data(index, role=Qt.ItemDataRole.UserRole)

        if isinstance(item, SceneItem):
            self.scenes[item.number] = SelectedScene(item, selected)

            children = [ model.index(i, 0, index) for i in range(model.rowCount(index))]
            for child_index in children:
                self.AppendItem(model, child_index, False)

        elif isinstance(item, BatchItem):
            batch = SelectedBatch(item, selected)
            #TODO: line selection
            batch.originals = item.originals
            batch.translated = item.translated

            if not self.scenes.get(item.scene):
                self.AppendItem(model, model.parent(index), False)

            self.scenes[item.scene][item.number] = batch
            
    def __str__(self):
        if self.scene_numbers:
            return f"{self.str_scenes} with {self.str_originals} and {self.str_translated} in {self.str_batches}"
        elif self.batch_numbers:
            return f"{self.str_originals} and {self.str_translated} in {self.str_batches}"
        elif self.translated:
            return f"{self.str_originals} and {self.str_translated}"
        elif self.originals:
            return f"{self.str_originals}"
        else:
            return "Nothing selected"
        
    def __repr__(self):
        return str(self)

    @property
    def str_scenes(self):
        return self._count(len(self.scene_numbers), "scene", "scenes")

    @property
    def str_batches(self):
        return self._count(len(self.batch_numbers), "batch", "batches")

    @property
    def str_originals(self):
        return self._count(len(self.originals), "original", "originals")

    @property
    def str_translated(self):
        return self._count(len(self.translated), "translation", "translations")

    def _count(self, num, singular, plural):
        if num == 0:
            return f"No {plural}"
        elif num == 1:
            return f"1 {singular}"
        else:
            return f"{num} {plural}"

