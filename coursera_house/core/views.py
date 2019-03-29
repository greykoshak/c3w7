from django.urls import reverse_lazy
from django.views.generic import FormView

from .models import Setting
from .form import ControllerForm
from  .tasks import get_controller_state
from django.http import HttpResponse


class ControllerView(FormView):
    form_class = ControllerForm
    template_name = 'core/control.html'
    success_url = reverse_lazy('form')

    def get_context_data(self, **kwargs):
        context = super(ControllerView, self).get_context_data()
        context['data'] = self.get_initial()
        return context

    def get_initial(self):
        return get_controller_state()

    def form_valid(self, form):
        # This method is called when valid form data has been POSTed.
        # It should return an HttpResponse.

        if form.is_valid():
            bedroom_target_temperature = form.cleaned_data['bedroom_target_temperature']
            hot_water_target_temperature = form.cleaned_data['hot_water_target_temperature']
            bedroom_light = form.cleaned_data['bedroom_light']
            bathroom_light = form.cleaned_data['bathroom_light']
            print(f"----------------------{bedroom_target_temperature}")
            print(f"----------------------{hot_water_target_temperature}")
            print(f"----------------------{bedroom_light}")
            print(f"----------------------{bathroom_light}")
        else:
            return HttpResponse(status=500)

        return super(ControllerView, self).form_valid(form)
