from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import ValidationError
from .forecast import get_seven_day_forecast

class SevenDayRiskForecastView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        ward = (request.query_params.get('ward') or '').strip()
        if not ward:
            raise ValidationError({'ward': 'Ward name is required as ?ward= parameter.'})
        forecast = get_seven_day_forecast(ward)
        return Response({'ward': ward, 'forecast': forecast})
