from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    oidc_issuer: str = "http://mock-id-dienst:8081"
    oidc_jwks_url: str = "http://mock-id-dienst:8081/jwks"
    oidc_audience: str = "patient-intake"
    auth_disabled: bool = False

    fhir_base_url: str = "http://mock-kis-fhir:8080/fhir"
    # Dev: the same HAPI mock serves KIS and ePA. Prod: TI gateway/Konnektor URL of the ePA FHIR API.
    epa_base_url: str = "http://mock-kis-fhir:8080/fhir"
    epa_timeout_s: float = 10.0

    kim_smtp_host: str = "mock-kim-cm"
    kim_smtp_port: int = 2525
    kim_sender: str = "intake@praxis.kim.test"
    kim_recipient: str = "arzt@praxis.kim.test"

    llm_base_url: str = ""
    llm_model: str = "llama3.1"


settings = Settings()
