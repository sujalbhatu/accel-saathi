// One icon set for the whole app (Lucide, drawn at one stroke weight), so no screen falls back to emoji.
import React from 'react'
import {
  Activity, ArrowLeft, ArrowRight, ArrowUp, BadgeCheck, Briefcase, Building2, CalendarCheck, Cctv, Check, ChevronRight, CircleCheck,
  CircleX, Clock, Cloud, CloudUpload, CreditCard, Factory, FileText, Gauge, Globe, GraduationCap, Handshake, Headset, Home, IdCard,
  Languages, Lightbulb, Lock, Mail, MapPin, MessageCircle, MessageSquare, Mic, Minus, Network, Phone, PhoneCall, Pill, Plus, QrCode,
  RadioTower, ReceiptText, RefreshCw, Router, Scissors, Shield, ShieldCheck, ShoppingBag, Smartphone, Sparkles, Stethoscope, Store,
  Timer, Trash2, TriangleAlert, Truck, Upload, Users, UtensilsCrossed, Volume2, VolumeX, Wifi, Wrench, Zap,
} from 'lucide-react'

const SET = {
  activity: Activity, back: ArrowLeft, next: ArrowRight, send: ArrowUp, verified: BadgeCheck, building: Building2, calendar: CalendarCheck,
  check: Check, chevron: ChevronRight, ok: CircleCheck, fail: CircleX, clock: Clock, doc: FileText, globe: Globe, handshake: Handshake,
  support: Headset, home: Home, id: IdCard, languages: Languages, idea: Lightbulb, lock: Lock, pin: MapPin, chat: MessageCircle, mic: Mic,
  minus: Minus, plus: Plus, qr: QrCode, bill: ReceiptText, refresh: RefreshCw, shield: ShieldCheck, sparkles: Sparkles, timer: Timer,
  trash: Trash2, warn: TriangleAlert, upload: Upload, people: Users, speak: Volume2, mute: VolumeX, wrench: Wrench, zap: Zap, factory: Factory,
}

// What the owner said the business is (the value the advisor's first chips send)
const BUSINESS = {
  'Kirana store': Store, Salon: Scissors, Pharmacy: Pill, 'Dental clinic': Stethoscope, 'CA firm': Briefcase, 'Coaching centre': GraduationCap,
  'Restaurant chain': UtensilsCrossed, 'Apparel retail chain': ShoppingBag, 'Auto-parts unit': Factory,
}

// The needs checklist, by the key the advisor uses
const NEED = {
  payments: CreditCard, whatsapp: MessageCircle, sms: MessageSquare, cctv: Cctv, email: Mail, security: Shield, backup: CloudUpload,
  website: Globe, guest_wifi: Wifi, failover: RadioTower, calls: Phone, tollfree: PhoneCall, static_ip: MapPin, iot: Gauge, fleet: Truck,
  central_mgmt: Network, firewall: ShieldCheck,
}

// Catalogue products, by id
const PRODUCT = {
  P01: Router, P02: Router, P03: Router, P04: RadioTower, P05: Network, P06: Network, P07: Smartphone, P08: Smartphone, P09: RefreshCw,
  P10: Network, P11: MapPin, P12: Phone, P13: PhoneCall, P14: MessageSquare, P15: MessageCircle, P16: Mail, P17: Cloud, P18: Globe,
  P19: CreditCard, P20: Shield, P21: ShieldCheck, P22: Wifi, P23: Cctv, P24: Gauge, P25: Truck,
}

const DOC = { gst_certificate: ReceiptText, udyam_certificate: Factory, signatory_id: IdCard, address_proof: Home }

export default function Icon({ name, size = 18, ...rest }) {
  const C = SET[name]
  return C ? <C size={size} strokeWidth={1.9} aria-hidden {...rest} /> : null
}

const from = (map, fallback) => function Mapped({ id, size = 18, ...rest }) {
  const C = map[id] || fallback
  return <C size={size} strokeWidth={1.9} aria-hidden {...rest} />
}

export const BusinessIcon = from(BUSINESS, Building2)
export const NeedIcon = from(NEED, Sparkles)
export const ProductIcon = from(PRODUCT, Sparkles)
export const DocIcon = from(DOC, FileText)
