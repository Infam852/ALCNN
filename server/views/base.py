import os

from flask.views import MethodView
import torch
from torch.utils.data import DataLoader

from dral.models import Model
from dral.config.config_manager import ConfigManager
from dral.datasets import UnlabelledDataset, LabelledDataset
from dral.utils import get_resnet18_default_transforms

from server.exceptions import AnnotationException


MODEL_PATH = os.path.join('data', 'saved_models', 'test_model.pt')
CONFIG_NAME = 'testset'


class BaseView(MethodView):
    def __init__(self):
        self.cm = ConfigManager(CONFIG_NAME)


class MLView(BaseView):
    def __init__(self):
        super().__init__()
        self.unl_dataset = UnlabelledDataset(
            self.cm.get_unl_annotations_path(),
            get_resnet18_default_transforms())
        self.unl_loader = DataLoader(
            self.unl_dataset, batch_size=self.cm.get_batch_size(),
            shuffle=True, num_workers=2)
        self.train_dataset = LabelledDataset(
            self.cm.get_train_annotations_path(),
            self.cm.get_n_labels(),
            get_resnet18_default_transforms())
        self.test_dataset = LabelledDataset(
            self.cm.get_test_annotations_path(),
            self.cm.get_n_labels(),
            get_resnet18_default_transforms())
        self.train_loader = None
        self.test_loader = None

    # csv with annotations can not be empty
    def get_train_loader(self):
        self.train_dataset.reload()
        self._fail_if_loader_is_empty(self.train_dataset)

        if not self.train_loader:
            self.train_loader = DataLoader(
                self.train_dataset, batch_size=self.cm.get_batch_size(),
                shuffle=True, num_workers=0)
        return self.train_loader

    def get_test_loader(self):
        self.train_dataset.reload()
        self._fail_if_loader_is_empty(self.train_dataset)

        if not self.test_loader:
            self.test_loader = DataLoader(
                self.test_dataset, batch_size=self.cm.get_batch_size(),
                shuffle=True, num_workers=0)
        return self.test_loader

    def _fail_if_loader_is_empty(self, loader):  # !TODO could be static or moved somewhere
        if not len(loader):
            raise AnnotationException(
                'Annotation csv file has to contain at least one sample')

    def load_model(self):
        model = Model.load(MODEL_PATH)
        return Model(model)

    def save_model(self, model):
        torch.save(model, MODEL_PATH)