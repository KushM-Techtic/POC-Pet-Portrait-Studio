import { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Col,
  Image,
  Layout,
  message,
  Progress,
  Row,
  Space,
  Spin,
  Tag,
  Typography,
} from 'antd'
import type { Product, ProductsResponse, GenerateResponse, ShopifyMetafield } from './types'
import './App.css'

const { Header: AntHeader, Content } = Layout
const { Title, Text } = Typography

const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:9000'

function toFriendlyMessage(error: unknown): string {
  const msg = error instanceof Error ? error.message : String(error)
  if (/failed to fetch|network|networkerror/i.test(msg)) {
    return 'Please check your connection and try again.'
  }
  if (/404|not found/i.test(msg)) {
    return 'The requested resource was not found.'
  }
  if (/429|too many requests|rate limit/i.test(msg)) {
    return 'Too many requests. Please try again in a moment.'
  }
  if (/502|503|504|bad gateway|service unavailable/i.test(msg)) {
    return 'The service is temporarily unavailable. Please try again later.'
  }
  if (/401|403|unauthorized|forbidden/i.test(msg)) {
    return "You don't have permission to perform this action."
  }
  return 'Something went wrong. Please try again.'
}

function numericProductId(gidOrId: string): string {
  const parts = gidOrId.split('/')
  return parts[parts.length - 1] || gidOrId
}

function App() {
  const [data, setData] = useState<ProductsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [generatingAll, setGeneratingAll] = useState(false)
  const [genById, setGenById] = useState<
    Record<
      string,
      { status: 'idle' | 'loading' | 'done' | 'error'; url?: string; error?: string }
    >
  >({})

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    fetch(`${backendUrl}/products`)
      .then(async (r) => {
        if (!r.ok) {
          const txt = await r.text()
          throw new Error(txt || `HTTP ${r.status}`)
        }
        return (await r.json()) as ProductsResponse
      })
      .then((json) => {
        if (cancelled) return
        setData(json)
      })
      .catch((e: unknown) => {
        if (cancelled) return
        setError(e instanceof Error ? e.message : String(e))
        message.error(toFriendlyMessage(e))
      })
      .finally(() => {
        if (cancelled) return
        setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  const products = useMemo(() => data?.products ?? [], [data])

  function setDoneFromOutput(productId: string, outputUrl: string) {
    const absUrl = outputUrl.startsWith('http') ? outputUrl : `${backendUrl}${outputUrl}`
    setGenById((prev) => ({ ...prev, [productId]: { status: 'done', url: absUrl } }))
  }

  async function onGenerate(product: Product) {
    const id = product.id
    setGenById((prev) => ({ ...prev, [id]: { status: 'loading' } }))

    try {
      const pid = numericProductId(id)
      const r = await fetch(`${backendUrl}/generate/${encodeURIComponent(pid)}`, {
        method: 'POST',
      })
      if (!r.ok) {
        const txt = await r.text()
        throw new Error(txt || `HTTP ${r.status}`)
      }
      const json = (await r.json()) as GenerateResponse
      setDoneFromOutput(id, json.output.url)
      message.success(`Generated: ${product.title}`)
    } catch (e: unknown) {
      setGenById((prev) => ({ ...prev, [id]: { status: 'error' } }))
      message.error(toFriendlyMessage(e))
    }
  }

  async function onGenerateAll() {
    if (products.length === 0) return
    setGeneratingAll(true)
    try {
      const r = await fetch(`${backendUrl}/generate-all`, { method: 'POST' })
      if (!r.ok) {
        const txt = await r.text()
        throw new Error(txt || `HTTP ${r.status}`)
      }
      const json = (await r.json()) as {
        count: number
        tag: string
        results: Array<{
          status: 'ok' | 'error'
          product: { id: string; title?: string; handle?: string }
          output?: { url: string; filename: string; mime_type: string }
          error?: string
        }>
      }

      let ok = 0
      let failed = 0
      for (const item of json.results) {
        if (item.status === 'ok' && item.output?.url) {
          ok += 1
          setDoneFromOutput(item.product.id, item.output.url)
        } else {
          failed += 1
        }
      }

      if (failed > 0 && ok > 0) {
        message.success(`Generated ${ok} product(s). ${failed} failed.`)
      } else if (failed > 0) {
        message.error(`Failed to generate ${failed} product(s).`)
      } else {
        message.success(`Generated ${ok} product(s).`)
      }
    } catch (e: unknown) {
      message.error(toFriendlyMessage(e))
    } finally {
      setGeneratingAll(false)
    }
  }

  const doneCount = useMemo(
    () => Object.values(genById).filter((s) => s.status === 'done').length,
    [genById]
  )
  const anyLoading = useMemo(
    () => Object.values(genById).some((s) => s.status === 'loading'),
    [genById]
  )

  return (
    <Layout className="app-layout">
      <AntHeader className="app-header">
        <div className="header-inner">
          <div className="brand">
            <Title level={3} className="brand-title">
              Pet Portrait Studio
            </Title>
            <Text className="brand-subtitle">Shopify · AI-generated portraits</Text>
          </div>
          <Space align="center" size="middle">
            {!loading && products.length > 0 && (
              <Tag className="count-badge">{products.length} products</Tag>
            )}
            <Button
              type="primary"
              size="large"
              onClick={onGenerateAll}
              loading={generatingAll}
              disabled={loading || products.length === 0 || anyLoading}
              className="generate-all-btn"
            >
              {generatingAll ? `Generating ${doneCount}/${products.length}…` : 'Generate all'}
            </Button>
          </Space>
        </div>
      </AntHeader>

      <Content className="app-content">
        {generatingAll && products.length > 0 && (
          <div className="progress-bar-wrap">
            <Progress
              percent={Math.round((doneCount / products.length) * 100)}
              showInfo
              status="active"
            />
          </div>
        )}

        {error ? (
          <Alert
            type="error"
            showIcon
            message="Couldn't load products"
            description={
              <Text type="secondary" style={{ fontSize: 12 }}>
                {toFriendlyMessage(error)} Make sure the backend is running at{' '}
                <code>{backendUrl}</code>.
              </Text>
            }
            className="error-alert"
          />
        ) : null}

        {loading && products.length === 0 ? (
          <div className="loading-center">
            <Spin tip="Loading products…" size="large" />
          </div>
        ) : (
          <Spin spinning={loading} tip="Loading products…" size="large">
            <div className="products-section">
              <Row gutter={[20, 20]}>
                {products.map((p) => (
                  <Col xs={24} sm={24} md={12} lg={8} key={p.id}>
                    <Card className="product-card" bordered={false}>
                      <div className="card-title-wrap">
                        <Title level={5} className="card-title">
                          {p.title}
                        </Title>
                        <Text type="secondary" className="card-handle">
                          {p.handle}
                        </Text>
                      </div>
                      {(p.tags?.length ?? 0) > 0 && (
                        <Space wrap size={[0, 6]} className="card-tags">
                          {(p.tags || []).map((t) => (
                            <Tag key={t} className="product-tag">
                              {t}
                            </Tag>
                          ))}
                        </Space>
                      )}
                      <Row gutter={[8, 8]} className="previews-row">
                        {renderPreviewCol('Pet', p.metafields?.pet_image)}
                        {renderPreviewCol('Template', p.metafields?.template_image)}
                        {renderPreviewCol('Style', p.metafields?.style_image)}
                      </Row>
                      <div className="card-actions">
                        <Button
                          type="primary"
                          onClick={() => onGenerate(p)}
                          loading={genById[p.id]?.status === 'loading'}
                          disabled={generatingAll}
                        >
                          {genById[p.id]?.status === 'loading'
                            ? 'Generating…'
                            : genById[p.id]?.status === 'done'
                              ? 'Regenerate'
                              : 'Generate'}
                        </Button>
                      </div>
                      {genById[p.id]?.status === 'done' && genById[p.id]?.url && (
                        <div className="generated-wrap">
                          <Text type="secondary" className="generated-label">
                            Generated portrait
                          </Text>
                          <Image
                            src={genById[p.id]?.url}
                            alt="Generated"
                            className="generated-img"
                            preview={{ src: genById[p.id]?.url }}
                          />
                        </div>
                      )}
                  </Card>
                  </Col>
                ))}
              </Row>
            </div>
          </Spin>
        )}
      </Content>
    </Layout>
  )
}

export default App

function renderPreviewCol(label: string, mf: ShopifyMetafield | undefined) {
  if (!mf || !mf.url) return null
  const lower = mf.url.toLowerCase()
  const isImage =
    lower.includes('.png') ||
    lower.includes('.jpg') ||
    lower.includes('.jpeg') ||
    lower.includes('.webp')

  if (!isImage) {
    return (
      <Col span={8} key={label}>
        <a href={mf.url} target="_blank" rel="noreferrer" className="preview-link">
          {label}
        </a>
      </Col>
    )
  }

  return (
    <Col span={8} key={label}>
      <div className="preview-thumb">
        <Image
          src={mf.url}
          alt={label}
          preview={{ src: mf.url }}
          className="preview-img"
        />
        <span className="preview-label">{label}</span>
      </div>
    </Col>
  )
}
