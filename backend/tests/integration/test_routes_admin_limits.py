class TestUserLimits:
    def test_admin_can_view_a_user_s_default_limits_and_usage(self, admin_client):
        client, fake_db = admin_client(
            current_user={"uid": "admin-1", "role": "ADMIN"},
            users={"u1": {"email": "a@a.com", "role": "USER"}},
        )

        response = client.get("/admin/users/u1/limits")

        assert response.status_code == 200
        body = response.json()
        assert body["limits"] == {
            "daily_token_limit": 100_000,
            "daily_search_limit": 30,
            "monthly_token_limit": 2_000_000,
            "monthly_search_limit": 600,
        }
        assert body["usage"] == {
            "daily_tokens": 0,
            "daily_searches": 0,
            "monthly_tokens": 0,
            "monthly_searches": 0,
        }
        assert "daily_reset_at" in body
        assert "monthly_reset_at" in body

    def test_admin_can_set_a_user_s_limits(self, admin_client):
        client, fake_db = admin_client(
            current_user={"uid": "admin-1", "role": "ADMIN"},
            users={"u1": {"email": "a@a.com", "role": "USER"}},
        )

        response = client.patch(
            "/admin/users/u1/limits",
            json={
                "daily_token_limit": 5000,
                "daily_search_limit": 10,
                "monthly_token_limit": 100_000,
                "monthly_search_limit": 200,
            },
        )

        assert response.status_code == 200
        assert response.json()["limits"] == {
            "daily_token_limit": 5000,
            "daily_search_limit": 10,
            "monthly_token_limit": 100_000,
            "monthly_search_limit": 200,
        }
        stored = fake_db.collection("usage_limits").document("u1").get().to_dict()
        assert stored["daily_token_limit"] == 5000

    def test_admin_cannot_view_or_edit_an_admin_s_limits(self, admin_client):
        client, _fake_db = admin_client(
            current_user={"uid": "admin-1", "role": "ADMIN"},
            users={"a2": {"email": "other-admin@a.com", "role": "ADMIN"}},
        )

        get_response = client.get("/admin/users/a2/limits")
        patch_response = client.patch(
            "/admin/users/a2/limits",
            json={
                "daily_token_limit": 1,
                "daily_search_limit": 1,
                "monthly_token_limit": 1,
                "monthly_search_limit": 1,
            },
        )

        assert get_response.status_code == 403
        assert patch_response.status_code == 403

    def test_super_admin_can_edit_an_admin_s_limits(self, admin_client):
        client, fake_db = admin_client(
            current_user={"uid": "super-1", "role": "SUPER_ADMIN"},
            users={"a2": {"email": "other-admin@a.com", "role": "ADMIN"}},
        )

        response = client.patch(
            "/admin/users/a2/limits",
            json={
                "daily_token_limit": 1,
                "daily_search_limit": 1,
                "monthly_token_limit": 1,
                "monthly_search_limit": 1,
            },
        )

        assert response.status_code == 200

    def test_super_admin_account_itself_cannot_be_edited(self, admin_client):
        client, _fake_db = admin_client(
            current_user={"uid": "super-1", "role": "SUPER_ADMIN"},
            users={"super-2": {"email": "s2@a.com", "role": "SUPER_ADMIN"}},
        )

        response = client.patch(
            "/admin/users/super-2/limits",
            json={
                "daily_token_limit": 1,
                "daily_search_limit": 1,
                "monthly_token_limit": 1,
                "monthly_search_limit": 1,
            },
        )

        assert response.status_code == 403

    def test_returns_404_for_an_unknown_user(self, admin_client):
        client, _fake_db = admin_client(current_user={"uid": "admin-1", "role": "ADMIN"}, users={})

        response = client.get("/admin/users/ghost/limits")

        assert response.status_code == 404

    def test_plain_user_cannot_view_or_edit_limits(self, admin_client):
        client, _fake_db = admin_client(current_user={"uid": "u1", "role": "USER"}, users={})

        get_response = client.get("/admin/users/u1/limits")
        patch_response = client.patch(
            "/admin/users/u1/limits",
            json={
                "daily_token_limit": 1,
                "daily_search_limit": 1,
                "monthly_token_limit": 1,
                "monthly_search_limit": 1,
            },
        )

        assert get_response.status_code == 403
        assert patch_response.status_code == 403

    def test_negative_limits_are_rejected(self, admin_client):
        client, _fake_db = admin_client(
            current_user={"uid": "admin-1", "role": "ADMIN"},
            users={"u1": {"email": "a@a.com", "role": "USER"}},
        )

        response = client.patch(
            "/admin/users/u1/limits",
            json={
                "daily_token_limit": -1,
                "daily_search_limit": 10,
                "monthly_token_limit": 100_000,
                "monthly_search_limit": 200,
            },
        )

        assert response.status_code == 422
