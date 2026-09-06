from dataclasses import dataclass

@dataclass(frozen=True)
class PacsStatus:
    name:str
    status:str
    operations:list[str]
    external_transmission_enabled:bool=False

class OrthancAdapter:
    """Safe REST contract. Network calls remain disabled until explicitly configured."""
    def __init__(self,base_url:str|None=None,enabled:bool=False):self.base_url=base_url;self.enabled=enabled
    def status(self)->PacsStatus:return PacsStatus("Orthanc REST","CONFIGURED" if self.base_url else "NOT_CONFIGURED",["studies","instances","retrieve"],False)

class DicomWebAdapter:
    """QIDO/WADO/STOW interface contract without implicit external transmission."""
    def __init__(self,base_url:str|None=None,stow_enabled:bool=False):self.base_url=base_url;self.stow_enabled=stow_enabled
    def status(self)->PacsStatus:return PacsStatus("DICOMweb","CONFIGURED" if self.base_url else "NOT_CONFIGURED",["QIDO-RS","WADO-RS","STOW-RS"],bool(self.base_url and self.stow_enabled))

def integration_status()->dict:
    adapters=[OrthancAdapter().status(),DicomWebAdapter().status()]
    return {"pacs":"NOT_CONFIGURED","adapters":[x.__dict__ for x in adapters],"external_transmission":"DISABLED_BY_DEFAULT","synthetic_test_supported":True}
