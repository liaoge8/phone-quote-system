"""冒烟测试：SQLite + TestClient 跑全流程。

流程：健康检查 → 登录 → 建商品 → 追加价格记录 → 本月政策价 →
国补计算（可享/不可享）→ 入网台账 CRUD → 销量存档与对比 → 停产沉底 → 删除
"""
import os
import tempfile

# 必须在 import app 之前设置：用临时 SQLite 库，避免污染 data.db
_tmpdir = tempfile.mkdtemp(prefix="quote_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmpdir}/test.db"
os.environ["ADMIN_PASSWORD"] = "8888"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def main() -> None:
    with TestClient(app) as client:
        # 1. 健康检查（无需登录）
        r = client.get("/api/health")
        assert r.status_code == 200 and r.json()["status"] == "ok", r.text
        print("1. 健康检查 OK")

        # 2. 错误密码登录应 401
        r = client.post("/api/auth/login", json={"password": "wrong"})
        assert r.status_code == 401, r.text
        print("2. 错误密码拒绝 OK")

        # 3. 未带 token 访问应 401
        r = client.get("/api/products")
        assert r.status_code == 401, r.text
        print("3. 未鉴权拦截 OK")

        # 4. 正确登录拿 token
        r = client.post("/api/auth/login", json={"password": "8888"})
        assert r.status_code == 200, r.text
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
        print("4. 登录 OK")

        # 5. 新建商品（含全部配置和颜色一次录入）
        product_payload = {
            "brand": "华为",
            "model": "Mate 90 Pro",
            "intro": "测试机型介绍",
            "selling_points": ["麒麟芯片", "卫星通信"],
            "variants": [
                {"name": "12GB+256GB", "official_price": 6499,
                 "normal_price": 5999, "adjusted_price": 5799},
                {"name": "12GB+512GB", "official_price": 6999,
                 "normal_price": 6499, "adjusted_price": 6299},
            ],
            "colors": ["曜石黑", "云白色"],
            "virtual_price": 6200,
        }
        r = client.post("/api/products", json=product_payload, headers=headers)
        assert r.status_code == 201, r.text
        pid = r.json()["id"]
        assert r.json()["virtual_price"] == 6200
        print(f"5. 新建商品 OK（id={pid}）")

        # 6. 追加价格记录：虚拟价 → 正常价 → 调价 → 政策价
        for ptype, price, note in [
            ("virtual", 6200, "首次进货"),
            ("normal", 5999, ""),
            ("adjusted", 5799, "双11调价"),
            ("policy", 5599, "2026-11 政策"),
        ]:
            r = client.post(
                f"/api/products/{pid}/prices",
                json={"variant": "12GB+256GB", "type": ptype,
                      "price": price, "note": note},
                headers=headers,
            )
            assert r.status_code == 201, r.text
        r = client.get(f"/api/products/{pid}/prices", headers=headers)
        assert len(r.json()) == 4, r.text
        print("6. 价格记录追加 OK（4 条，只追加不覆盖）")

        # 7. 本月政策价（含政策解释）
        r = client.post(
            f"/api/products/{pid}/policy",
            json={"month": "2026-11", "final_price": 5599,
                  "explanation": "11 月渠道政策：直降 200 元，限时两周。"},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        assert r.json()["explanation"].startswith("11 月渠道政策")
        print("7. 本月政策价 OK（含政策解释）")

        # 8. 国补计算：官网价 5299 → 补贴 min(794.85, 500)=500，国补价 4799
        r = client.get(f"/api/products/{pid}/subsidy",
                       params={"official_price": 5299}, headers=headers)
        assert r.status_code == 200, r.text
        s = r.json()
        assert s["eligible"] is True
        assert s["subsidy"] == 500 and s["capped"] is True
        assert s["final_price"] == 4799
        assert "15%" in s["formula"]
        print(f"8. 国补计算 OK（可享：{s['formula']}，补贴 500，国补价 4799）")

        # 9. 国补计算：官网价 6500 → 不可享
        r = client.get(f"/api/products/{pid}/subsidy",
                       params={"official_price": 6500}, headers=headers)
        assert r.json()["eligible"] is False, r.text
        print("9. 国补计算 OK（超 6000 不可享）")

        # 10. 入网台账 CRUD
        r = client.post(
            "/api/intel/tenna",
            json={"phone_model": "小米 19 Pro", "tenna_model": "25128PNA1C",
                  "specs": "6.8 英寸 / 骁龙 8 Elite Gen6"},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        tid = r.json()["id"]
        r = client.put(f"/api/intel/tenna/{tid}", json={"status": "followed"},
                       headers=headers)
        assert r.json()["status"] == "followed", r.text
        r = client.get("/api/intel/tenna", headers=headers)
        assert len(r.json()) == 1, r.text
        print("10. 入网台账 CRUD OK")

        # 11. 销量存档 + 对比：2025-10（2000 万部）vs 2026-10（2185.6 万部）
        for month, shipments in [("2025-10", 2000.0), ("2026-10", 2185.6)]:
            r = client.post(
                "/api/sales/archives",
                json={"month": month, "shipments": shipments, "source": "信通院"},
                headers=headers,
            )
            assert r.status_code == 201, r.text
        r = client.get("/api/sales/compare", params={"m1": "2025-10", "m2": "2026-10"},
                       headers=headers)
        c = r.json()
        assert c["diff"] == 185.6 and abs(c["change_rate"] - 0.0928) < 1e-4, c
        print(f"11. 销量对比 OK（差值 {c['diff']} 万部，涨跌幅 {c['change_rate']:.2%}）")

        # 12. 停产商品自动沉底
        r = client.post(
            "/api/products",
            json={"brand": "苹果", "model": "iPhone 15", "status": "discontinued"},
            headers=headers,
        )
        pid2 = r.json()["id"]
        r = client.get("/api/products", headers=headers)
        ids = [p["id"] for p in r.json()]
        assert ids[-1] == pid2, ids  # 停产的在最后
        print("12. 停产沉底 OK")

        # 13. 删除商品
        r = client.delete(f"/api/products/{pid2}", headers=headers)
        assert r.status_code == 204, r.text
        print("13. 删除商品 OK")

    print("\n冒烟测试全部通过 ✔")


if __name__ == "__main__":
    main()
