from adc_aiopg.repository import PostgresAccessLayer
from adc_aiopg.repository.dao import TableDescriptor

import models as m
from models.client_app import ClientApp
from models.credential import Credential
from models.identity import AuthIdentity
from models.identity_external_link import AuthIdentityExternalLink
from models.logins import Login
from models.oauth_provider import AuthOauthProvider
from models.otp_challenge import AuthOtpChallenge
from models.session import Session


class DAO(PostgresAccessLayer, metadata=m.base.meta):
    identities = TableDescriptor[AuthIdentity](AuthIdentity, table_name="auth_identities")
    credentials = TableDescriptor[Credential](Credential, table_name="auth_credentials")
    sessions = TableDescriptor[Session](Session, table_name="auth_sessions")
    client_apps = TableDescriptor[ClientApp](ClientApp, table_name="auth_client_apps")
    oauth_providers = TableDescriptor[AuthOauthProvider](AuthOauthProvider, table_name="auth_oauth_providers")
    otp_challenges = TableDescriptor[AuthOtpChallenge](AuthOtpChallenge, table_name="auth_otp_challenges")
    identity_external_links = TableDescriptor[AuthIdentityExternalLink](
        AuthIdentityExternalLink,
        table_name="auth_identity_external_links",
    )
    logins = TableDescriptor[Login](Login, table_name="auth_logins")
