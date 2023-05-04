from django.views import generic
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from .models import Monitor
from django.conf import settings
from monitor.forms import AddMonitorForm

class IndexView(LoginRequiredMixin, generic.ListView):
    template_name = 'monitor/index.html'

    def get_queryset(self):
        results = Monitor.objects.filter(user=self.request.user)
        return results

    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)
        return context


class DetailView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'monitor/detail.html'

    def get_context_data(self, **kwargs):
        context = super(DetailView, self).get_context_data(**kwargs)
        context['device'] = get_object_or_404(
            Monitor, pk=kwargs['device_id'], user=self.request.user)
        return context


class AddMonitorView(LoginRequiredMixin, generic.FormView):
    template_name = 'monitor/addmonitor.html'
    form_class = AddMonitorForm
    success_url = '/monitor'

    def get_context_data(self, **kwargs):
        context = super(AddMonitorView, self).get_context_data(**kwargs)
        return context

    def form_valid(self, form):
        device = form.cleaned_data['device']
        device.associate_and_publish_associated_msg(self.request.user)

        return super(AddMonitorView, self).form_valid(form)
