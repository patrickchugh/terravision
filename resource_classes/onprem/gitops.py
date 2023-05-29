from . import _OnPrem


class _Gitops(_OnPrem):
    _type = "gitops"
    _icon_dir = "resource_images/onprem/gitops"


class Argocd(_Gitops):
    _icon = "argocd.png"


class Flagger(_Gitops):
    _icon = "flagger.png"


class Flux(_Gitops):
    _icon = "flux.png"


# Aliases

ArgoCD = Argocd
