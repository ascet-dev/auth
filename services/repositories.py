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
    identities = TableDescriptor[AuthIdentity](AuthIdentity)
    credentials = TableDescriptor[Credential](Credential)
    sessions = TableDescriptor[Session](Session)
    client_apps = TableDescriptor[ClientApp](ClientApp)
    oauth_providers = TableDescriptor[AuthOauthProvider](AuthOauthProvider)
    otp_challenges = TableDescriptor[AuthOtpChallenge](AuthOtpChallenge)
    identity_external_links = TableDescriptor[AuthIdentityExternalLink](AuthIdentityExternalLink)
    logins = TableDescriptor[Login](Login)
