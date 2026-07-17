from .models import Etablissement


def etablissement(request):
    return {"etablissement": Etablissement.get_solo()}
