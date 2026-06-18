import asyncio
import sys

sys.path.append('C:/Users/HP/Desktop/final-year/SOMALI-NLP-RESEARCH/web')

from backend.database.mongo import connect, close
from backend.services.auth_service import authenticate_user, ensure_demo_user


async def main() -> None:
    try:
        await connect()
        await ensure_demo_user()
        token = await authenticate_user('demo@somalinlp.local', 'Demo12345!')
        print('TOKEN_OK', bool(token and token.get('access_token')))
        assert token is not None
        assert 'access_token' in token
    finally:
        await close()


if __name__ == '__main__':
    asyncio.run(main())
