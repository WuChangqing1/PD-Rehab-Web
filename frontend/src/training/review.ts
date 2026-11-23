import {ref} from 'vue'
import {ReviewOffers,type TrainingReference} from './reviewOffers'
const offers=new ReviewOffers()
export const reviewOffer=ref<TrainingReference|null>(null)
let handoff:TrainingReference|null=null
export function offerTrainingReview(row:TrainingReference,saved=true,interrupted=false){if(offers.offer(row,saved,interrupted))reviewOffer.value=offers.take()}
export function prepareReview(){if(!reviewOffer.value)return;handoff=reviewOffer.value;reviewOffer.value=null}
export function takeReview(){const row=handoff;handoff=null;return row}
export function clearTrainingReviews(){offers.clear();reviewOffer.value=null;handoff=null}
