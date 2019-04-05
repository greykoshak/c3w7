from django.http import HttpResponse
from django.urls import reverse_lazy
from django.views.generic import FormView

from .form import ControllerForm
from .tasks import CleverSystem, AccessBD, ControlCmd


class ControllerView(FormView):
    form_class = ControllerForm
    template_name = 'core/control.html'
    success_url = reverse_lazy('form')
    states = None

    def get(self, request, *args, **kwargs):
        self.states = CleverSystem.get_controller_state()
        if CleverSystem.ret_get_code != 200:
            return HttpResponse(status=502)
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.states = CleverSystem.get_controller_state()
        if CleverSystem.ret_get_code != 200:
            return HttpResponse(status=502)
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ControllerView, self).get_context_data()
        context['data'] = self.states

        return context

    def get_initial(self):
        # Set initial values from DB to form
        bedroom_target_temperature = AccessBD.get_value_DB("bedroom_target_temperature", 21)
        hot_water_target_temperature = AccessBD.get_value_DB("hot_water_target_temperature", 80)

        return {"bedroom_target_temperature": bedroom_target_temperature,
                "hot_water_target_temperature": hot_water_target_temperature,
                "bedroom_light": self.states['bedroom_light'],
                "bathroom_light": self.states['bathroom_light'],
                }

    def form_valid(self, form):
        # This method is called when valid form data has been POSTed.
        # It should return an HttpResponse.

        bedroom = form.cleaned_data['bedroom_target_temperature']
        AccessBD.set_value_DB("bedroom_target_temperature", bedroom)

        hot_water = form.cleaned_data['hot_water_target_temperature']
        AccessBD.set_value_DB("hot_water_target_temperature", hot_water)

        bedroom_light = form.cleaned_data['bedroom_light']
        bathroom_light = form.cleaned_data['bathroom_light']

        new_states = {}
        if not ControlCmd.is_smoke_detector(self.states, new_states):
            if bathroom_light != self.states['bathroom_light']:
                new_states['bathroom_light'] = bathroom_light
            if bedroom_light != self.states['bedroom_light']:
                new_states['bedroom_light'] = bedroom_light

            ControlCmd.is_needed_change_temperature(self.states, new_states)
            ControlCmd.is_needed_hot_water(self.states, new_states)

        change_state = CleverSystem.create_states(new_states)
        CleverSystem.put_controller_state(change_state)

        return super(ControllerView, self).form_valid(form)
