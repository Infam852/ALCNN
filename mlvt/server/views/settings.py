from flask import render_template

from mlvt.server.views.base import BaseView, ModelIO
from mlvt.server.views.annotation import AnnotationsView


class SettingsView(BaseView, ModelIO):
    def search(self):
        model_summary = self._get_model_summary()
        av = AnnotationsView()
        annotation_summary = av.search()[0]
        return render_template("settings.html.j2", model=model_summary,
                               annotation=annotation_summary)

    def _get_model_summary(self):
        model_wrapper = self.load_model(self.cm.get_model_trained())
        model = model_wrapper.model_conv
        model_summary = {}
        model_summary['Model name'] = model.__class__.__name__
        model_summary['Number of parameters'] = \
            sum(p.numel() for p in model.parameters())
        model_summary['Number of conv layers'] = 0
        model_summary['FC layers'] = 0
        model_summary['Learning rate'] = model_wrapper.get_lr()
        model_summary['Loss function'] = str(model_wrapper.criterion)[:-2]

        for name, module in model.named_modules():
            if 'Conv' in module.__class__.__name__:
                model_summary['Number of conv layers'] += 1
            if 'Linear' in module.__class__.__name__:
                model_summary['FC layers'] += 1
        return model_summary