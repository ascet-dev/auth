from adc_aiopg.repository import PGDataAccessObject, PostgresAccessLayer, TableDescriptor

import models as m
from models.client_app import ClientApp
from models.credential import Credential
from models.identity import AuthIdentity
from models.identity_external_link import AuthIdentityExternalLink
from models.logins import Login
from models.oauth_provider import AuthOauthProvider
from models.otp_challenge import AuthOtpChallenge
from models.session import Session


class DAO(PostgresAccessLayer, metadata=m.base.meta):  # type: ignore[call-arg]
    identities = TableDescriptor(PGDataAccessObject.from_model(AuthIdentity, "auth_identities"))
    credentials = TableDescriptor(PGDataAccessObject.from_model(Credential, "auth_credentials"))
    sessions = TableDescriptor(PGDataAccessObject.from_model(Session, "auth_sessions"))
    client_apps = TableDescriptor(PGDataAccessObject.from_model(ClientApp, "auth_client_apps"))
    oauth_providers = TableDescriptor(PGDataAccessObject.from_model(AuthOauthProvider, "auth_oauth_providers"))
    otp_challenges = TableDescriptor(PGDataAccessObject.from_model(AuthOtpChallenge, "auth_otp_challenges"))
    identity_external_links = TableDescriptor(
        PGDataAccessObject.from_model(AuthIdentityExternalLink, "auth_identity_external_links"),
    )
    logins = TableDescriptor(PGDataAccessObject.from_model(Login, "auth_logins"))
