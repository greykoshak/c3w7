from django.http import HttpResponse
from django.urls import reverse_lazy
from django.views.generic import FormView

from .form import ControllerForm
from .tasks import get_controller_state, get_value, put_controller_state


class ControllerView(FormView):
    form_class = ControllerForm
    template_name = 'core/control.html'
    success_url = reverse_lazy('form')
    states = get_controller_state()

    def get_context_data(self, **kwargs):
        context = super(ControllerView, self).get_context_data()
        context['data'] = get_controller_state()

        return context

    def get_initial(self):
        # Set initial values from DB to form
        bedroom_target_temperature = get_value("bedroom_target_temperature", None, 21)
        hot_water_target_temperature = get_value("hot_water_target_temperature", None, 80)

        return {"bedroom_target_temperature": bedroom_target_temperature,
                "hot_water_target_temperature": hot_water_target_temperature,
                "bedroom_light": self.states['bedroom_light'],
                "bathroom_light": self.states['bathroom_light'],
                }

    def form_valid(self, form):
        # This method is called when valid form data has been POSTed.
        # It should return an HttpResponse.

        if form.is_valid():

            bedroom = form.cleaned_data['bedroom_target_temperature']
            bedroom_target_temperature = get_value("bedroom_target_temperature", bedroom, 21)

            hot_water = form.cleaned_data['hot_water_target_temperature']
            hot_water_target_temperature = get_value("hot_water_target_temperature", hot_water, 80)

            bedroom_light = form.cleaned_data['bedroom_light']
            bathroom_light = form.cleaned_data['bathroom_light']

            new_states = {}
            if not self.states['smoke_detector']:
                if bathroom_light != self.states['bathroom_light']:
                    new_states['bathroom_light'] = "true" if bathroom_light else "false"
                if bedroom_light != self.states['bedroom_light']:
                    new_states['bedroom_light'] = "true" if bedroom_light else "false"
                if (self.states['bedroom_temperature'] > bedroom_target_temperature * 1.1) and \
                        not self.states['air_conditioner']:
                    new_states['air_conditioner'] = "true"
                if (self.states['boiler_temperature'] < hot_water_target_temperature * 0.9) and \
                        not self.states['boiler'] and not self.states['leak_detector']:
                    new_states['boiler'] = "true"

            if new_states:
                change_state = dict()
                change_state["controllers"] = list()

                for key, value in new_states.items():
                    change_state['controllers'].append({"name": key, "value": value})

                put_controller_state(change_state)
        else:
            return HttpResponse(status=502)

        return super(ControllerView, self).form_valid(form)
