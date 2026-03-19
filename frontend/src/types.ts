export type ShopifyMetafield = null | {
  type?: string
  value?: string | null
  url?: string | null
}

export type Product = {
  id: string
  title: string
  handle: string
  tags: string[]
  metafields?: Record<string, ShopifyMetafield>
}

export type ProductsResponse = {
  count: number
  tag: string
  products: Product[]
}

export type GenerateResponse = {
  output: {
    url: string
    filename: string
    mime_type: string
  }
  product: {
    id: string
    title: string
    handle: string
  }
}
