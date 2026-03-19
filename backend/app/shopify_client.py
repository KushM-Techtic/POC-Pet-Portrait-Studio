from __future__ import annotations

import httpx


class ShopifyClient:
    def __init__(self, *, store_domain: str, api_version: str, access_token: str) -> None:
        self._url = f"https://{store_domain}/admin/api/{api_version}/graphql.json"
        self._headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        }

    async def fetch_products_by_tag(self, *, tag: str, first: int = 25, metafield_namespace: str, metafield_keys: list[str]) -> list[dict]:
        # Build aliased metafield lookups. This is widely supported versus `metafields(identifiers: ...)`,
        # which isn't available on some schemas/versions.
        #
        # Example:
        #   pet_image: metafield(namespace:"custom", key:"pet_image") { ... }
        metafield_fields = "\n                ".join(
            [
                f'{k}: metafield(namespace: "{metafield_namespace}", key: "{k}") {{\n'
                f"                  namespace\n"
                f"                  key\n"
                f"                  type\n"
                f"                  value\n"
                f"                  reference {{\n"
                f"                    __typename\n"
                f"                    ... on MediaImage {{ image {{ url }} }}\n"
                f"                    ... on GenericFile {{ url }}\n"
                f"                  }}\n"
                f"                }}\n"
                for k in metafield_keys
            ]
        )
        query = """
        query POCProducts($first: Int!, $query: String!) {
          products(first: $first, query: $query) {
            edges {
              node {
                id
                title
                handle
                tags
                %s
              }
            }
          }
        }
        """ % metafield_fields
        variables = {"first": first, "query": f"tag:{tag}"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(self._url, headers=self._headers, json={"query": query, "variables": variables})
            resp.raise_for_status()
            data = resp.json()

        if "errors" in data:
            raise RuntimeError(f"Shopify GraphQL errors: {data['errors']}")

        edges = data["data"]["products"]["edges"]
        return [self._normalize_product(e["node"], metafield_keys=metafield_keys) for e in edges]

    async def fetch_product_by_id(self, *, product_gid: str, metafield_namespace: str, metafield_keys: list[str]) -> dict:
        metafield_fields = "\n                ".join(
            [
                f'{k}: metafield(namespace: "{metafield_namespace}", key: "{k}") {{\n'
                f"                  namespace\n"
                f"                  key\n"
                f"                  type\n"
                f"                  value\n"
                f"                  reference {{\n"
                f"                    __typename\n"
                f"                    ... on MediaImage {{ image {{ url }} }}\n"
                f"                    ... on GenericFile {{ url }}\n"
                f"                  }}\n"
                f"                }}\n"
                for k in metafield_keys
            ]
        )

        query = """
        query ProductById($id: ID!) {
          product(id: $id) {
            id
            title
            handle
            tags
            %s
          }
        }
        """ % metafield_fields

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                self._url,
                headers=self._headers,
                json={"query": query, "variables": {"id": product_gid}},
            )
            resp.raise_for_status()
            data = resp.json()

        if "errors" in data:
            raise RuntimeError(f"Shopify GraphQL errors: {data['errors']}")

        node = data.get("data", {}).get("product")
        if not node:
            raise RuntimeError("Product not found")
        return self._normalize_product(node, metafield_keys=metafield_keys)

    @staticmethod
    def _normalize_product(node: dict, *, metafield_keys: list[str]) -> dict:
        """
        Convert Shopify aliased metafields into a keyed dict and normalize file URLs.
        """
        meta_out: dict[str, object] = {}
        for key in metafield_keys:
            mf = node.get(key)
            if not mf:
                meta_out[key] = None
                continue
            value = mf.get("value")
            ref = mf.get("reference") or {}
            url = None
            if ref.get("__typename") == "MediaImage":
                img = (ref.get("image") or {})
                url = img.get("url")
            elif ref.get("__typename") == "GenericFile":
                url = ref.get("url")

            meta_out[key] = {
                "type": mf.get("type"),
                "value": value,
                "url": url,
            }

        return {
            "id": node.get("id"),
            "title": node.get("title"),
            "handle": node.get("handle"),
            "tags": node.get("tags") or [],
            "metafields": meta_out,
        }

