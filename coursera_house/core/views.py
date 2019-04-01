from django.http import HttpResponse
from django.urls import reverse_lazy
from django.views.generic import FormView
from requests import RequestException

from .form import ControllerForm
from .tasks import get_controller_state, get_value_DB, set_value_DB, put_controller_state


class ControllerView(FormView):
    form_class = ControllerForm
    template_name = 'core/control.html'
    success_url = reverse_lazy('form')
    states = get_controller_state()

    def get(self, request, *args, **kwargs):
        self.states = get_controller_state()
        if not self.states:
            return HttpResponse(status=502)
        return super().get(request, *args, **kwargs)

    # def post(self, request, *args, **kwargs):
    #     try:
    #         self.states = get_controller_state()
    #     except (RequestException, KeyError, ValueError):
    #         return HttpResponse(status=502)
    #
    #     return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ControllerView, self).get_context_data()
        context['data'] = self.states

        return context

    def get_initial(self):
        # Set initial values from DB to form
        bedroom_target_temperature = get_value_DB("bedroom_target_temperature", 21)
        hot_water_target_temperature = get_value_DB("hot_water_target_temperature", 80)

        return {"bedroom_target_temperature": bedroom_target_temperature,
                "hot_water_target_temperature": hot_water_target_temperature,
                "bedroom_light": self.states['bedroom_light'],
                "bathroom_light": self.states['bathroom_light'],
                }

    def form_valid(self, form):
        # This method is called when valid form data has been POSTed.
        # It should return an HttpResponse.

        bedroom = form.cleaned_data['bedroom_target_temperature']
        bedroom_target_temperature = set_value_DB("bedroom_target_temperature", bedroom)

        hot_water = form.cleaned_data['hot_water_target_temperature']
        hot_water_target_temperature = set_value_DB("hot_water_target_temperature", hot_water)

        bedroom_light = form.cleaned_data['bedroom_light']
        bathroom_light = form.cleaned_data['bathroom_light']

        new_states = {}
        if not self.states['smoke_detector']:
            if bathroom_light != self.states['bathroom_light']:
                new_states['bathroom_light'] = bathroom_light
            if bedroom_light != self.states['bedroom_light']:
                new_states['bedroom_light'] = bedroom_light
            if (self.states['bedroom_temperature'] > int(bedroom_target_temperature * 1.1)) and \
                    not self.states['air_conditioner']:
                new_states['air_conditioner'] = True
            elif self.states['bedroom_temperature'] <= int(bedroom_target_temperature * 0.9) and \
                    not self.states['air_conditioner']:
                new_states['air_conditioner'] = False
            if (self.states['boiler_temperature'] <= int(hot_water_target_temperature * 0.9)) and \
                    not self.states['boiler'] and not self.states['leak_detector']:
                new_states['boiler'] = True
            elif (self.states['boiler_temperature'] > int(hot_water_target_temperature * 1.1)) and \
                    self.states['boiler']:
                new_states['boiler'] = False

        if new_states:
            change_state = dict()
            change_state["controllers"] = list()

            for key, value in new_states.items():
                change_state['controllers'].append({"name": key, "value": value})

            put_controller_state(change_state)

        return super(ControllerView, self).form_valid(form)
