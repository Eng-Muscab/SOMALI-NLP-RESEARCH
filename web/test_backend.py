import sys, asyncio
sys.path.append('c:/Users/HP/Desktop/final-year/SOMALI-NLP-RESEARCH/web')
from backend.database.mongo import ping
async def main():
    ok = await ping()
    print('Mongo ping:', ok)
    # test health endpoint via httpx
    import httpx
    async with httpx.AsyncClient() as client:
        r = await client.get('http://127.0.0.1:8000/api/health')
        print('Health status code:', r.status_code)
        print('Health json:', r.json())
asyncio.run(main())
