/* DEMO DATA ONLY. Replaced later by the Python/MySQL backend through js/api-service.js. */
const _d = n => new Date(Date.now() + n * 864e5).toISOString().slice(0, 10);
const MOCK = {
  facilities: [
    { id: 'F01', name: 'City General Hospital', address: '12 MG Road, Bengaluru', contact: '080-5550-0101' },
    { id: 'F02', name: 'Rural Primary Health Centre', address: 'Hosur Road, Anekal', contact: '080-5550-0102' },
    { id: 'F03', name: 'Sunrise Community Clinic', address: '4th Block, Jayanagar', contact: '080-5550-0103' },
    { id: 'F04', name: 'Lakeside Medical Centre', address: 'Ulsoor Lake Road', contact: '080-5550-0104' },
    { id: 'F05', name: 'Metro Care Pharmacy Hub', address: 'Whitefield Main Road', contact: '080-5550-0105' }
  ],
  medicines: [
    { id: 'M01', name: 'Paracetamol 500 mg' }, { id: 'M02', name: 'Amoxicillin 250 mg' },
    { id: 'M03', name: 'Insulin Glargine' }, { id: 'M04', name: 'Metformin 500 mg' },
    { id: 'M05', name: 'ORS Sachets' }, { id: 'M06', name: 'Azithromycin 500 mg' }, { id: 'M07', name: 'Cetirizine 10 mg' }
  ],
  batches: [
    { batchId: 'B101', medicineId: 'M01', facilityId: 'F01', qty: 120, expiry: _d(-12), stock: 'Available' },
    { batchId: 'B102', medicineId: 'M01', facilityId: 'F01', qty: 120, expiry: _d(21), stock: 'Available' },
    { batchId: 'B103', medicineId: 'M01', facilityId: 'F05', qty: 180, expiry: _d(59), stock: 'Available' },
    { batchId: 'B104', medicineId: 'M01', facilityId: 'F03', qty: 0, expiry: _d(120), stock: 'Out of Stock' },
    { batchId: 'B105', medicineId: 'M01', facilityId: 'F02', qty: 250, expiry: _d(300), stock: 'Available' },
    { batchId: 'B106', medicineId: 'M02', facilityId: 'F01', qty: 0, expiry: _d(40), stock: 'Out of Stock' },
    { batchId: 'B107', medicineId: 'M02', facilityId: 'F04', qty: 30, expiry: _d(75), stock: 'Available' },
    { batchId: 'B108', medicineId: 'M03', facilityId: 'F01', qty: 25, expiry: _d(30), stock: 'Available' },
    { batchId: 'B109', medicineId: 'M03', facilityId: 'F04', qty: 0, expiry: _d(200), stock: 'Out of Stock' },
    { batchId: 'B110', medicineId: 'M04', facilityId: 'F02', qty: 400, expiry: _d(180), stock: 'Available' },
    { batchId: 'B111', medicineId: 'M05', facilityId: 'F01', qty: 60, expiry: _d(-30), stock: 'Available' },
    { batchId: 'B112', medicineId: 'M05', facilityId: 'F04', qty: 0, expiry: _d(90), stock: 'Out of Stock' },
    { batchId: 'B113', medicineId: 'M06', facilityId: 'F05', qty: 75, expiry: _d(14), stock: 'Available' },
    { batchId: 'B114', medicineId: 'M07', facilityId: 'F03', qty: 200, expiry: _d(500), stock: 'Available' },
    { batchId: 'B115', medicineId: 'M04', facilityId: 'F05', qty: 35, expiry: _d(8), stock: 'Available' }
  ],
  requests: [
    { id: 'R001', medicineId: 'M01', facilityId: 'F02', qty: 200, allocated: 200, date: _d(-20), status: 'Fulfilled' },
    { id: 'R002', medicineId: 'M02', facilityId: 'F03', qty: 150, allocated: 90, date: _d(-15), status: 'Partially Fulfilled' },
    { id: 'R006', medicineId: 'M04', facilityId: 'F01', qty: 100, allocated: 0, date: _d(-10), status: 'Rejected' },
    { id: 'R003', medicineId: 'M01', facilityId: 'F04', qty: 300, allocated: 0, date: _d(-6), status: 'Pending' },
    { id: 'R004', medicineId: 'M03', facilityId: 'F02', qty: 40, allocated: 0, date: _d(-4), status: 'Pending' },
    { id: 'R005', medicineId: 'M05', facilityId: 'F03', qty: 500, allocated: 0, date: _d(-2), status: 'Pending' }
  ],
  transactions: [
    { id: 'T001', requestId: 'R001', medicineId: 'M01', batchId: 'B090', sourceId: 'F01', destId: 'F02', qty: 120, date: _d(-18) },
    { id: 'T002', requestId: 'R001', medicineId: 'M01', batchId: 'B091', sourceId: 'F05', destId: 'F02', qty: 80, date: _d(-18) },
    { id: 'T003', requestId: 'R002', medicineId: 'M02', batchId: 'B092', sourceId: 'F01', destId: 'F03', qty: 90, date: _d(-13) }
  ],
  /* STATIC EXAMPLE RESULTS (demonstration only). The real list comes from the Python backend,
     already in expiry-priority order (insertion sort) with suggested quantities (greedy). */
  eligible: {
    R003: [{ batchId: 'B102', eligible: true, suggested: 120 }, { batchId: 'B103', eligible: true, suggested: 180 },
      { batchId: 'B101', eligible: false, reason: 'Expired medicine is never redistributed.' },
      { batchId: 'B104', eligible: false, reason: 'Zero quantity in stock.' },
      { batchId: 'B105', eligible: true, suggested: 250 }],
    R004: [{ batchId: 'B108', eligible: true, suggested: 25 }, { batchId: 'B109', eligible: false, reason: 'Zero quantity in stock.' }],
    R005: [{ batchId: 'B111', eligible: false, reason: 'Expired medicine is never redistributed.' }, { batchId: 'B112', eligible: false, reason: 'Zero quantity in stock.' }],
    R002: [{ batchId: 'B107', eligible: true, suggested: 30 }, { batchId: 'B106', eligible: false, reason: 'Zero quantity in stock.' }]
  }
};
